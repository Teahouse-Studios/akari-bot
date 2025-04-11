"""利用阿里云API检查字符串是否合规。

在使用前，请在配置文件中填写`check_access_key_id`和`check_access_key_secret`，以便进行鉴权。
"""

import base64
import datetime
import hashlib
import hmac
import time
from typing import Union, List, Dict

import httpx
import orjson as json
from tenacity import retry, wait_fixed, stop_after_attempt

from core.builtins import Bot
from core.config import Config
from core.database.local import DirtyWordCache
from core.logger import Logger


def hash_hmac(key, code):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode("utf-8")


def computeMD5hash(my_string):
    m = hashlib.md5(usedforsecurity=False)
    m.update(my_string.encode("gb2312"))
    return m.hexdigest()


def parse_data(result: dict, additional_text=None) -> Dict:
    original_content = content = result["content"]
    status = True
    for itemResult in result["results"]:
        if itemResult["suggestion"] == "block":
            for itemDetail in itemResult["details"]:
                if "contexts" in itemDetail:
                    for itemContext in itemDetail["contexts"]:
                        _offset = 0
                        if "positions" in itemContext:
                            for pos in itemContext["positions"]:
                                filter_words_length = pos["endPos"] - pos["startPos"]
                                reason = f"[I18N:check.redacted,reason={itemDetail["label"]}]"
                                content = (content[: pos["startPos"] + _offset] +
                                           reason + content[pos["endPos"] + _offset:])
                                if additional_text:
                                    content += "\n" + additional_text + "\n"
                                _offset += len(reason) - filter_words_length
                        else:
                            content = f"[I18N:check.redacted,reason={itemDetail["label"]}]"
                        status = False
                else:
                    content = f"[I18N:check.redacted.all,reason={itemDetail["label"]}]"

                    if additional_text:
                        content += "\n" + additional_text + "\n"
                    status = False
    return {"content": content, "status": status, "original": original_content}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(*text: Union[str, List[str]], additional_text=None) -> List[Dict]:
    """检查字符串。

    :param text: 字符串（List/Union）。
    :param additional_text: 附加文本，若指定则会在返回的消息中附加此文本。
    :returns: 经过审核后的字符串。不合规部分会被替换为`<REDACTED:原因>`，全部不合规则是`<ALL REDACTED:原因>`。
    """
    access_key_id = Config("check_access_key_id", cfg_type=str, secret=True)
    access_key_secret = Config("check_access_key_secret", cfg_type=str, secret=True)
    text = list(text)
    text = text[0] if len(text) == 1 and isinstance(text[0], list) else text  # 检查是否为嵌套的消息链
    if not access_key_id or not access_key_secret or not Bot.Info.dirty_word_check:
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
                    query_list[q][pq] = parse_data(cache.result, additional_text=additional_text)

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
        body = {
            "scenes": ["antispam"],
            "tasks": [{"dataId": f"Nullcat is god {time.time()}", "content": x} for x in call_api_list_],
        }
        root = "https://green.cn-shanghai.aliyuncs.com"
        url = "/green/text/scan"

        gmt_format = "%a, %d %b %Y %H:%M:%S GMT"
        date = datetime.datetime.now(datetime.UTC).strftime(gmt_format)
        nonce = f"LittleC sb {time.time()}"
        content_md5 = base64.b64encode(
            hashlib.md5(json.dumps(body), usedforsecurity=False).digest()
        ).decode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Content-MD5": content_md5,
            "Date": date,
            "x-acs-version": "2018-05-09",
            "x-acs-signature-nonce": nonce,
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
            resp = await client.post(f"{root}{url}", content=json.dumps(body))
            if resp.status_code == 200:
                result = json.loads(resp.content)
                Logger.debug(result)
                for item in result["data"]:
                    content = item["content"]
                    for n in call_api_list[content]:
                        query_list[n][content] = parse_data(item, additional_text=additional_text)
                    await DirtyWordCache.create(desc=content, result=item)
            else:
                raise ValueError(resp.text)

    results = []
    Logger.debug(query_list)
    for q in query_list.values():
        for result in q.values():
            results.append(result)
    return results


async def check_bool(*text: Union[str, List[str]]) -> bool:
    """检查字符串是否合规。

    :param text: 字符串（List/Union）。
    :returns: 字符串是否合规。
    """
    chk = await check(*text)
    for x in chk:
        if not x["status"]:
            return True
    return False


def rickroll() -> str:
    """合规检查失败时输出的Rickroll消息。

    :returns: Rickroll消息。
    """
    if rickroll_msg := Config("rickroll_msg", cfg_type=str) and Config("enable_rickroll", True):
        return rickroll_msg
    return "[I18N:error.message.chain.unsafe]"
