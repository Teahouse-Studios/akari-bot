"""利用阿里云API检查字符串是否合规。

在使用前，应该在配置中填写"check_access_key_id"和"check_access_key_secret"以便进行鉴权。
"""

import base64
import datetime
import hashlib
import hmac
import time
from typing import Union, List, Dict

import aiohttp
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


def parse_data(
    result: dict, msg: Bot.MessageSession = None, additional_text=None
) -> Dict:
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
                                if not msg:
                                    reason = f"<REDACTED:{itemDetail['label']}>"
                                else:
                                    reason = msg.locale.t(
                                        "check.redacted", reason=itemDetail["label"]
                                    )
                                content = (
                                    content[: pos["startPos"] + _offset]
                                    + reason
                                    + content[pos["endPos"] + _offset :]
                                )
                                if additional_text:
                                    content += "\n" + additional_text + "\n"
                                _offset += len(reason) - filter_words_length
                        else:
                            if not msg:
                                content = f"<REDACTED:{itemDetail['label']}>"
                            else:
                                content = msg.locale.t(
                                    "check.redacted", reason=itemDetail["label"]
                                )
                        status = False
                else:
                    if not msg:
                        content = f"<ALL REDACTED:{itemDetail['label']}>"
                    else:
                        content = msg.locale.t(
                            "check.redacted.all", reason=itemDetail["label"]
                        )

                    if additional_text:
                        content += "\n" + additional_text + "\n"
                    status = False
    return {"content": content, "status": status, "original": original_content}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(
    *text: Union[str, List[str]], msg: Bot.MessageSession = None, additional_text=None
) -> List[Dict]:
    """检查字符串。

    :param text: 字符串（List/Union）。
    :param msg: 消息会话，若指定则本地化返回的消息。
    :param additional_text: 附加文本，若指定则会在返回的消息中附加此文本。
    :returns: 经过审核后的字符串。不合规部分会被替换为`<REDACTED:原因>`，全部不合规则是`<ALL REDACTED:原因>`。
    """
    access_key_id = Config("check_access_key_id", cfg_type=str, secret=True)
    access_key_secret = Config("check_access_key_secret", cfg_type=str, secret=True)
    text = list(text)
    text = (
        text[0] if len(text) == 1 and isinstance(text[0], list) else text
    )  # 检查是否为嵌套的消息链
    if not access_key_id or not access_key_secret or not Bot.Info.dirty_word_check:
        Logger.warning("Dirty words filter was disabled, skip.")
        query_list = []
        for t in text:
            query_list.append({"content": t, "status": True, "original": t})
        Logger.debug(query_list)
        return query_list
    if not text:
        return []
    query_list = {}
    count = 0
    for t in text:
        if t == "":
            query_list.update(
                {count: {t: {"content": t, "status": True, "original": t}}}
            )
        else:
            query_list.update({count: {t: False}})
        count += 1
    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                cache = DirtyWordCache(pq)
                if not cache.need_insert:
                    query_list.update(
                        {
                            q: {
                                pq: parse_data(
                                    cache.get(),
                                    msg=msg,
                                    additional_text=additional_text,
                                )
                            }
                        }
                    )
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
            "tasks": list(
                map(
                    lambda x: {
                        "dataId": "Nullcat is god {}".format(time.time()),
                        "content": x,
                    },
                    call_api_list_,
                )
            ),
        }
        client_info = "{}"
        root = "https://green.cn-shanghai.aliyuncs.com"
        url = "/green/text/scan?{}".format(client_info)

        gmt_format = "%a, %d %b %Y %H:%M:%S GMT"
        date = datetime.datetime.now(datetime.UTC).strftime(gmt_format)
        nonce = "LittleC sb {}".format(time.time())
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
        tmp = {
            "x-acs-version": "2018-05-09",
            "x-acs-signature-nonce": nonce,
            "x-acs-signature-version": "1.0",
            "x-acs-signature-method": "HMAC-SHA1",
        }
        sorted_header = {k: tmp[k] for k in sorted(tmp)}
        step1 = "\n".join(
            list(
                map(
                    lambda x: "{}:{}".format(x, sorted_header[x]),
                    list(sorted_header.keys()),
                )
            )
        )
        step2 = url
        step3 = "POST\napplication/json\n{contentMd5}\napplication/json\n{date}\n{step1}\n{step2}".format(
            contentMd5=content_md5, date=headers["Date"], step1=step1, step2=step2
        )
        sign = "acs {}:{}".format(access_key_id, hash_hmac(access_key_secret, step3))
        headers["Authorization"] = sign
        # 'Authorization': "acs {}:{}".format(access_key_id, sign)
        async with aiohttp.ClientSession(headers=headers) as session, session.post(
            "{}{}".format(root, url), data=json.dumps(body)
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                Logger.debug(result)
                for item in result["data"]:
                    content = item["content"]
                    for n in call_api_list[content]:
                        query_list.update(
                            {
                                n: {
                                    content: parse_data(
                                        item, msg=msg, additional_text=additional_text
                                    )
                                }
                            }
                        )
                    DirtyWordCache(content).update(item)
            else:
                raise ValueError(await resp.text())
    results = []
    Logger.debug(query_list)
    for x in query_list:
        for y in query_list[x]:
            results.append(query_list[x][y])
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


def rickroll(msg: Bot.MessageSession) -> str:
    """合规检查失败时输出的Rickroll消息。

    :param msg: 消息会话。
    :returns: Rickroll消息。
    """
    if Config("enable_rickroll", True) and Config("rickroll_msg", cfg_type=str):
        return msg.locale.t_str(Config("rickroll_msg", cfg_type=str))
    return msg.locale.t("error.message.chain.unsafe")
