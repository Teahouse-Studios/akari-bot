"""利用阿里云API检查字符串是否合规。

在使用前，请在配置文件中填写`check_access_key_id`和`check_access_key_secret`，以便进行鉴权。
"""

import asyncio
import base64
import datetime
import hashlib
import hmac
import re
import urllib.parse
import uuid
from typing import Union, List, Dict, Optional

import httpx
import orjson
from tenacity import retry, wait_fixed, stop_after_attempt

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext
from core.builtins.session.internal import MessageSession
from core.builtins.types import MessageElement
from core.config import Config
from core.database.local import DirtyWordCache
from core.logger import Logger

access_key_id = Config("check_access_key_id", cfg_type=str, secret=True)
access_key_secret = Config("check_access_key_secret", cfg_type=str, secret=True)
use_textscan_v1 = Config("check_use_textscan_v1", cfg_type=bool, default=False)


def hash_hmac(key, code):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode("utf-8")


def computeMD5hash(my_string):
    m = hashlib.md5(usedforsecurity=False)
    m.update(my_string.encode("gb2312"))
    return m.hexdigest()


def parse_data(original_content: str, result: dict, confidence: float = 60, additional_text=None) -> Dict:
    content = original_content
    status = True

    if use_textscan_v1:
        for itemResult in result["results"]:
            if float(itemResult["rate"]) >= confidence and itemResult["suggestion"] == "block":
                status = False
                for itemDetail in itemResult["details"]:
                    if "contexts" in itemDetail:
                        for itemContext in itemDetail["contexts"]:
                            _offset = 0
                            if "positions" in itemContext:
                                for pos in itemContext["positions"]:
                                    filter_words_length = pos["endPos"] - pos["startPos"]
                                    reason = str(I18NContext("check.redacted", reason=itemDetail["label"]))
                                    content = (content[: pos["startPos"] + _offset] +
                                               reason + content[pos["endPos"] + _offset:])
                                    _offset += len(reason) - filter_words_length
                            else:
                                content = str(I18NContext("check.redacted", reason=itemDetail["label"]))
                    else:
                        content = str(I18NContext("check.redacted", reason=itemDetail["label"]))
    else:
        if result["RiskLevel"] == "high":
            status = False
            for itemDetail in result["Result"]:
                if float(itemDetail["Confidence"]) >= confidence:
                    risk_words = itemDetail.get("RiskWords")
                    if risk_words:
                        risk_words = sorted(risk_words.split(","), key=len, reverse=True)
                        i18ncode_pattern = re.compile(r"\{I18N:[^}]*\}")
                        placeholders = [(m.start(), m.end()) for m in i18ncode_pattern.finditer(content)]

                        def is_in_placeholder(start, end):
                            for p_start, p_end in placeholders:
                                if start < p_end and end > p_start:
                                    return True
                            return False

                        for word in risk_words:
                            word = word.strip()
                            for match in re.finditer(re.escape(word), content):
                                start, end = match.start(), match.end()
                                if not is_in_placeholder(start, end):
                                    reason = str(I18NContext("check.redacted", reason=itemDetail["Label"]))
                                    content = content[:start] + reason + content[end:]
                                    shift = len(reason) - len(word)
                                    placeholders = [(s + shift if s > start else s, e + shift if e > start else e) for s, e in placeholders]
                    else:
                        content = str(I18NContext("check.redacted", reason=itemDetail["Label"]))

    if additional_text:
        content += "\n" + additional_text + "\n"
    return {"content": content, "status": status, "original": original_content}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(text: Union[str,
                            List[str],
                            List[MessageElement],
                            MessageElement,
                            MessageChain],
                session: Optional[MessageSession] = None,
                confidence: float = 60,
                additional_text: Optional[str] = None) -> List[Dict]:
    """检查字符串。

    :param text: 字符串（List/Union）。
    :param session: 消息会话，若指定则会在返回的消息中附加会话信息。
    :param additional_text: 附加文本，若指定则会在返回的消息中附加此文本。
    :returns: 经过审核后的字符串。不合规部分会被替换为`<REDACTED:原因>`，全部不合规则是`<ALL REDACTED:原因>`。
    """

    if isinstance(text, str):
        text = [text]
    if isinstance(text, MessageElement):
        text = [str(text)]
    if isinstance(text, (list, MessageChain)):
        text = [str(x) for x in text]

    if not access_key_id or not access_key_secret or not (session and session.session_info.require_check_dirty_words):
        Logger.warning("Dirty words filter was disabled, skip.")
        return [{"content": t, "status": True, "original": t} for t in text]

    if not text:
        return []

    query_list = {}
    for count, t in enumerate(text):
        query_list[count] = {t: {"content": t, "status": True, "original": t}} if t == "" else {t: False}

    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                cache = await DirtyWordCache.check(pq)
                if cache:
                    query_list[q][pq] = parse_data(pq, cache.result, confidence, additional_text)

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
            date = datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
            content_md5 = base64.b64encode(
                hashlib.md5(orjson.dumps(body), usedforsecurity=False).digest()
            ).decode("utf-8")
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
                                query_list[n][content] = parse_data(content, item, confidence, additional_text)
                            await DirtyWordCache.create(desc=content, result=item)
                    else:
                        raise ValueError(result["msg"])
                else:
                    raise ValueError(resp.text)
        else:
            root = "https://green-cip.cn-shanghai.aliyuncs.com"
            sem = asyncio.Semaphore(10)

            async def call_api(x: str):
                async with sem:
                    date = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                        "ServiceParameters": orjson.dumps(
                            {"dataId": str(uuid.uuid4()), "content": x}
                        ).decode("utf-8")
                    }

                    sorted_params = sorted(params.items(), key=lambda k: k[0])
                    step1 = "&".join(
                        f"{urllib.parse.quote(str(k), safe='-_.~')}="
                        f"{urllib.parse.quote(str(v), safe='-_.~')}"
                        for k, v in sorted_params
                    )
                    step2 = "POST&%2F&" + urllib.parse.quote(step1, safe='-_.~')
                    step3 = f"{access_key_secret}&"
                    signature = base64.b64encode(
                        hmac.new(step3.encode("utf-8"), step2.encode("utf-8"), hashlib.sha1).digest()
                    ).decode("utf-8")
                    params["Signature"] = signature

                    query_string = "&".join(
                        f"{k}={urllib.parse.quote(str(v), safe='-_.~')}" for k, v in params.items()
                    )

                    resp = await client.post(f"{root}/?{query_string}")
                    if resp.status_code == 200:
                        result = resp.json()
                        Logger.debug(result)
                        if result["Code"] == 200:
                            for n in call_api_list[x]:
                                query_list[n][x] = parse_data(x, result["Data"], confidence, additional_text)
                            await DirtyWordCache.create(desc=x, result=result["Data"])
                        else:
                            raise ValueError(result["Message"])
                    else:
                        raise ValueError(resp.text)

            async with httpx.AsyncClient() as client:
                await asyncio.gather(*(call_api(x) for x in call_api_list_))

    results = []
    Logger.debug(query_list)
    for q in query_list.values():
        for result in q.values():
            results.append(result)
    return results


async def check_bool(text: Union[str,
                                 List[str],
                                 List[MessageElement],
                                 MessageElement,
                                 MessageChain],
                     session: Optional[MessageSession] = None,
                     confidence: float = 60) -> bool:
    """检查字符串是否合规。

    :param text: 字符串（List/Union）。
    :returns: 字符串是否合规。
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
    rickroll_msg = Config("rickroll_msg", cfg_type=str)
    if Config("enable_rickroll", True) and rickroll_msg:
        return rickroll_msg
    return "{I18N:error.message.chain.unsafe}"
