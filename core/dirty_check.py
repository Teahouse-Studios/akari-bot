"""检查字符串是否合规，支持阿里云内容安全与自定义关键词过滤。

使用阿里云后端前，请在配置文件中填写`check_access_key_id`和`check_access_key_secret`以便鉴权。
"""

import asyncio
import base64
import hashlib
import hmac
import re
import time
import urllib.parse
import uuid

import httpx
import orjson
from tenacity import retry, wait_fixed, stop_after_attempt

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.session.internal import MessageSession
from core.builtins.types import MessageElement
from core.config.base import CoreConfig, CoreSecretConfig
from core.constants.path import dirty_words_path
from core.database.local import DirtyWordCache
from core.logger import Logger

access_key_id = CoreSecretConfig.check_access_key_id
access_key_secret = CoreSecretConfig.check_access_key_secret
use_textscan_v1 = CoreConfig.check_use_textscan_v1
local_first = CoreConfig.check_local_first

ALIYUN_BACKEND = "aliyun"
ALIYUN_SPLIT_CACHE_KEY = "_akari_split_results"
TEXT_CHUNK_SIZE = 600


def hash_hmac(key, code):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode("utf-8")


def parse_data(original_content: str, result: dict, confidence: float = 60, additional_text=None) -> dict:
    content = original_content

    replace_tasks = []
    block_all_due_to_empty_context = False
    global_reason_label = None

    if use_textscan_v1:
        for itemResult in result.get("results", []):
            if float(itemResult.get("rate", 0)) < confidence:
                continue

            for itemDetail in itemResult.get("details", []):
                label = itemDetail.get("label")
                contexts = itemDetail.get("contexts", [])

                if not contexts:
                    block_all_due_to_empty_context = True
                    global_reason_label = label
                    break

                for itemContext in contexts:
                    keyword = itemContext.get("context")
                    if keyword:
                        replace_tasks.append((str(keyword).strip(), label))
            if block_all_due_to_empty_context:
                break
    else:
        if result.get("RiskLevel") == "high":
            for itemDetail in result.get("Result", []):
                if float(itemDetail.get("Confidence", 0)) >= confidence:
                    risk_words = itemDetail.get("RiskWords")
                    label = itemDetail.get("Label")

                    if risk_words:
                        for word in risk_words.split(","):
                            if word:
                                replace_tasks.append((str(word).strip(), label))
                    else:
                        block_all_due_to_empty_context = True
                        global_reason_label = label
                        break

    if block_all_due_to_empty_context:
        content = str(I18NContext("check.redacted", reason=global_reason_label))
    elif replace_tasks:
        replace_tasks = sorted(replace_tasks, key=lambda x: len(x[0]), reverse=True)

        i18ncode_pattern = re.compile(r"\{I18N:[^}]*\}")
        placeholders = [(m.start(), m.end()) for m in i18ncode_pattern.finditer(content)]

        def is_in_placeholder(start, end):
            return any(start < p_end and end > p_start for p_start, p_end in placeholders)

        matches_to_replace = []
        replaced_intervals = []

        for word, label in replace_tasks:
            reason = str(I18NContext("check.redacted", reason=label))
            for match in re.finditer(re.escape(word), content):
                start, end = match.start(), match.end()

                # 检查是否在占位符内，或者是否与已知高优先级长词的替换区间重叠
                if is_in_placeholder(start, end):
                    continue
                if any(start < re_end and end > re_start for re_start, re_end in replaced_intervals):
                    continue

                matches_to_replace.append((start, end, reason))
                replaced_intervals.append((start, end))

        matches_to_replace = sorted(matches_to_replace, key=lambda x: x[0], reverse=True)

        for start, end, reason in matches_to_replace:
            content = content[:start] + reason + content[end:]

    if additional_text:
        content += "\n" + additional_text + "\n"

    return {"content": content, "status": content == original_content, "original": original_content}


def parse_aliyun_split_data(
    original_content: str,
    result: dict,
    confidence: float = 60,
    additional_text: str | None = None,
) -> dict:
    split_results = result.get(ALIYUN_SPLIT_CACHE_KEY)
    if not isinstance(split_results, list):
        raise ValueError("Invalid Aliyun split cache data")

    chunks = [original_content[i : i + TEXT_CHUNK_SIZE] for i in range(0, len(original_content), TEXT_CHUNK_SIZE)]
    if len(chunks) != len(split_results):
        raise ValueError("Aliyun split cache data does not match content chunks")

    parsed_results = [
        parse_data(chunk, split_result, confidence, additional_text)
        for chunk, split_result in zip(chunks, split_results, strict=True)
    ]
    return {
        "content": "".join(result["content"] for result in parsed_results),
        "status": all(result["status"] for result in parsed_results),
        "original": original_content,
    }


def load_keyword_rules() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}

    if not dirty_words_path.is_dir():
        return rules

    for file in sorted(dirty_words_path.glob("*.txt")):
        if not file.is_file():
            continue
        label = f"custom_{file.stem}"
        try:
            words = [line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, UnicodeDecodeError) as exc:
            Logger.warning(f"Failed to load dirty words from {file}: {exc}")
            continue
        if words:
            rules[label] = words

    return rules


def parse_keyword_data(
    original_content: str,
    keywords: dict[str, list[str] | tuple[str, ...] | set[str]],
    additional_text: str | None = None,
) -> dict:
    """使用自定义关键词对文本进行过滤。

    :param original_content: 原始文本。
    :param keywords: 以过滤标签为键、该标签下过滤词列表为值的字典。
                     命中的过滤词会被替换为`<REDACTED:标签>`。
    :param additional_text: 附加文本，若指定则会在返回的消息中附加此文本。
    :returns: 过滤后的字典。命中关键词时`status`为`False`。
    """
    content = original_content

    replace_tasks = []
    seen = set()
    for label, words in keywords.items():
        for word in words:
            word = str(word).strip()
            if word and word not in seen:
                seen.add(word)
                replace_tasks.append((word, label))

    if replace_tasks:
        replace_tasks.sort(key=lambda x: len(x[0]), reverse=True)

        i18ncode_pattern = re.compile(r"\{I18N:[^}]*\}")
        placeholders = [(m.start(), m.end()) for m in i18ncode_pattern.finditer(content)]

        def is_in_placeholder(start, end):
            return any(start < p_end and end > p_start for p_start, p_end in placeholders)

        matches_to_replace = []
        replaced_intervals = []

        for word, label in replace_tasks:
            reason = str(I18NContext("check.redacted", reason=label))
            for match in re.finditer(re.escape(word), content):
                start, end = match.start(), match.end()
                if is_in_placeholder(start, end):
                    continue
                if any(start < re_end and end > re_start for re_start, re_end in replaced_intervals):
                    continue
                matches_to_replace.append((start, end, reason))
                replaced_intervals.append((start, end))

        matches_to_replace = sorted(matches_to_replace, key=lambda x: x[0], reverse=True)

        for start, end, reason in matches_to_replace:
            content = content[:start] + reason + content[end:]

    if additional_text:
        content += "\n" + additional_text + "\n"

    return {"content": content, "status": content == original_content, "original": original_content}


def dirty_word_cache_namespace(backend: str) -> str:
    api_version = "textscan-v1" if use_textscan_v1 else "moderation-plus-v2"
    return f"{ALIYUN_BACKEND}:{api_version}"


async def _check_aliyun(texts: list[str], confidence: float = 60) -> list[dict]:
    """对文本列表执行阿里云内容安全审核。

    :param texts: 待审核的文本列表。
    :param confidence: 判定置信度阈值。
    :returns: 与输入顺序一致的审核结果字典列表。
    """
    cache_namespace = dirty_word_cache_namespace(ALIYUN_BACKEND)

    query_list = {}
    for count, t in enumerate(texts):
        query_list[count] = {t: {"content": t, "status": True, "original": t}} if t == "" else {t: False}

    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                try:
                    cache = await DirtyWordCache.check(pq, namespace=cache_namespace)
                    if cache:
                        if use_textscan_v1:
                            query_list[q][pq] = parse_data(pq, cache.result, confidence)
                        else:
                            query_list[q][pq] = parse_aliyun_split_data(pq, cache.result, confidence)
                except Exception:
                    Logger.warning("Failed to get cache, skip.")
                    Logger.exception()
    call_api_list = {}
    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                if pq not in call_api_list:
                    call_api_list.update({pq: []})
                call_api_list[pq].append(q)
    call_api_list_ = list(call_api_list)
    Logger.debug(call_api_list_)

    if call_api_list_:
        if use_textscan_v1:
            url = "/green/text/scan"
            root = "https://green.cn-shanghai.aliyuncs.com"
            body = {
                "scenes": ["antispam"],
                "tasks": [{"dataId": str(uuid.uuid4()), "content": x} for x in call_api_list_],
            }
            date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
            content_md5 = base64.b64encode(hashlib.md5(orjson.dumps(body), usedforsecurity=False).digest()).decode(
                "utf-8"
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Content-MD5": content_md5,
                "Date": date,
                "x-acs-version": "2018-05-09",
                "x-acs-signature-nonce": str(uuid.uuid4()),
                "x-acs-signature-version": "1.0",
                "x-acs-signature-method": "HMAC-SHA1",
            }
            sorted_header = {k: headers[k] for k in sorted(headers) if k.startswith("x-acs-")}
            step1 = "\n".join([f"{k}:{v}" for k, v in sorted_header.items()])
            step2 = url
            step3 = f"POST\napplication/json\n{content_md5}\napplication/json\n{date}\n{step1}\n{step2}"
            sign = f"acs {access_key_id}:{hash_hmac(access_key_secret, step3)}"
            headers["Authorization"] = sign

            async with httpx.AsyncClient(headers=headers) as client:
                resp = await client.post(f"{root}{url}", content=orjson.dumps(body))
                if resp.status_code == 200:
                    result = orjson.loads(resp.content)
                    Logger.debug(result)

                    if result["code"] == 200:
                        for item in result["data"]:
                            content = item["content"]
                            for n in call_api_list[content]:
                                query_list[n][content] = parse_data(content, item, confidence)
                            hash_id = DirtyWordCache.make_hash(content, cache_namespace)
                            await DirtyWordCache.update_or_create(
                                hash_id=hash_id,
                                defaults={"desc": content, "result": item},
                            )
                    else:
                        raise ValueError(result["msg"])
                else:
                    raise ValueError(resp.text)
        else:
            root = "https://green-cip.cn-shanghai.aliyuncs.com"
            sem = asyncio.Semaphore(10)

            split_results = {x: [] for x in call_api_list_}

            async def call_api(original_text: str, sub_text: str, index: int):
                async with sem:
                    date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    params = {
                        "Format": "JSON",
                        "Version": "2022-03-02",
                        "AccessKeyId": access_key_id,
                        "SignatureMethod": "Hmac-SHA1",
                        "Timestamp": date,
                        "SignatureVersion": "1.0",
                        "SignatureNonce": str(uuid.uuid4()),
                        "Action": "TextModerationPlus",
                        "Service": "comment_detection_pro",
                        "ServiceParameters": orjson.dumps({"dataId": str(uuid.uuid4()), "content": sub_text}).decode(
                            "utf-8"
                        ),
                    }

                    sorted_params = sorted(params.items(), key=lambda k: k[0])
                    step1 = "&".join(
                        f"{urllib.parse.quote(str(k), safe='-_.~')}={urllib.parse.quote(str(v), safe='-_.~')}"
                        for k, v in sorted_params
                    )
                    step2 = "POST&%2F&" + urllib.parse.quote(step1, safe="-_.~")
                    step3 = f"{access_key_secret}&"
                    signature = base64.b64encode(
                        hmac.new(step3.encode("utf-8"), step2.encode("utf-8"), hashlib.sha1).digest()
                    ).decode("utf-8")
                    params["Signature"] = signature

                    query_string = "&".join(f"{k}={urllib.parse.quote(str(v), safe='-_.~')}" for k, v in params.items())

                    resp = await client.post(f"{root}/?{query_string}")
                    if resp.status_code == 200:
                        result = resp.json()
                        Logger.debug(result)
                        if result["Code"] == 200:
                            parsed_sub = parse_data(sub_text, result["Data"], confidence)
                            split_results[original_text].append((index, parsed_sub, result["Data"]))
                        else:
                            raise ValueError(result["Message"])
                    else:
                        raise ValueError(resp.text)

            async with httpx.AsyncClient() as client:
                tasks = []
                for x in call_api_list_:
                    chunks = [x[i : i + TEXT_CHUNK_SIZE] for i in range(0, len(x), TEXT_CHUNK_SIZE)]
                    for idx, chunk in enumerate(chunks):
                        tasks.append(call_api(x, chunk, idx))

                await asyncio.gather(*tasks)

            for x, res_list in split_results.items():
                res_list.sort(key=lambda item: item[0])

                cache_result = {ALIYUN_SPLIT_CACHE_KEY: [result[2] for result in res_list]}
                final_parse_result = parse_aliyun_split_data(x, cache_result, confidence)

                for n in call_api_list[x]:
                    query_list[n][x] = final_parse_result

                if res_list:
                    try:
                        hash_id = DirtyWordCache.make_hash(x, cache_namespace)
                        await DirtyWordCache.update_or_create(
                            hash_id=hash_id,
                            defaults={"desc": x, "result": cache_result},
                        )
                    except Exception:
                        Logger.warning("Failed to create dirty word cache, skip.")
                        Logger.exception()
    results = []
    Logger.debug(query_list)
    for q in query_list.values():
        for result in q.values():
            results.append(result)
    return results


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(
    text: str | list[str] | list[MessageElement] | MessageElement | MessageChain,
    session: MessageSession | None = None,
    confidence: float = 60,
    additional_text: str | None = None,
    force=False,
) -> list[dict]:
    """检查字符串。

    本地关键词过滤优先执行：先对文本做本地词表过滤，再对过滤后的文本调用阿里云 API。
    默认所有文本都会经过第三方 API 二次过滤；开启`check_local_first`后，
    已被本地词表判定不合规的文本将跳过第三方 API 以节省费用，但本地词表覆盖不到的敏感词可能漏出。
    任一步判定不合规即视为不合规。

    :param text: 字符串（List/Union）。
    :param session: 消息会话，若指定则会在返回的消息中附加会话信息。
    :param additional_text: 附加文本，若指定则会在返回的消息中附加此文本。
    :returns: 经过审核后的字典列表。不合规部分会被替换为`<REDACTED:原因>`，全部不合规则是`<ALL REDACTED:原因>`。
    """

    if isinstance(text, str):
        text = [text]
    if isinstance(text, MessageElement):
        text = [str(text)]
    if isinstance(text, (list, MessageChain)):
        text = [str(x) for x in text]

    if not force and (session and not session.session_info.require_check_dirty_words):
        Logger.warning("Dirty words filter was disabled by session, skip.")
        return [{"content": t, "status": True, "original": t} for t in text]

    if not text:
        return []

    # 本地关键词过滤：存在词表文件时启用
    keywords = load_keyword_rules()
    keyword_results = [
        parse_keyword_data(t, keywords) if keywords else {"content": t, "status": True, "original": t} for t in text
    ]

    # 阿里云 API 过滤：默认对所有文本（含本地已命中的）发起请求，输入为本地过滤后的文本。
    # 开启 check_local_first 后，本地已判定不合规的文本将跳过第三方 API 以节省费用，
    # 但本地词表覆盖不到、需第三方 API 才能识别的敏感词可能漏出。
    aliyun_results: list[dict] = []
    if access_key_id and access_key_secret:
        if local_first:
            api_indices = [i for i, result in enumerate(keyword_results) if result["status"]]
        else:
            api_indices = list(range(len(keyword_results)))
        api_texts = [keyword_results[i]["content"] for i in api_indices]
        api_results = await _check_aliyun(api_texts, confidence) if api_texts else []
        api_result_map = dict(zip(api_indices, api_results, strict=True))
        aliyun_results = [
            api_result_map.get(i, {"content": result["content"], "status": True, "original": result["content"]})
            for i, result in enumerate(keyword_results)
        ]
    else:
        aliyun_results = [
            {"content": result["content"], "status": True, "original": result["content"]} for result in keyword_results
        ]

    results = []
    for keyword_result, aliyun_result in zip(keyword_results, aliyun_results, strict=True):
        status = keyword_result["status"] and aliyun_result["status"]
        content = aliyun_result["content"]
        if additional_text:
            content += "\n" + additional_text + "\n"
        results.append({"content": content, "status": status, "original": keyword_result["original"]})

    return results


async def check_bool(
    text: str | list[str] | list[MessageElement] | MessageElement | MessageChain,
    session: MessageSession | None = None,
    confidence: float = 60,
) -> bool:
    """检查字符串是否含有不合规内容。

    :param text: 字符串（List/Union）。
    :returns: 是否含有不合规内容，含有时为`True`。
    """
    chk = await check(text, session, confidence)
    for x in chk:
        if not x["status"]:
            return True
    return False


def rickroll() -> str:
    """合规检查失败时输出的Rickroll消息。

    :returns: Rickroll消息。
    """
    rickroll_msg = CoreConfig.rickroll_msg
    if CoreConfig.enable_rickroll and rickroll_msg:
        return rickroll_msg
    return "{I18N:error.message.chain.unsafe}"


__all__ = ["check", "check_bool", "rickroll"]
