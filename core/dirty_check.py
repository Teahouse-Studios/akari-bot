'''利用阿里云API检查字符串是否合规。

在使用前，应该在配置中填写"check_accessKeyId"和"check_accessKeySecret"以便进行鉴权。
'''
import base64
import datetime
import hashlib
import hmac
import json
import re
import time

import aiohttp
from tenacity import retry, wait_fixed, stop_after_attempt

from config import Config
from core.builtins import EnableDirtyWordCheck
from core.exceptions import NoReportException
from core.logger import Logger
from database.local import DirtyWordCache


def hash_hmac(key, code, sha1):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode('utf-8')


def computeMD5hash(my_string):
    m = hashlib.md5()
    m.update(my_string.encode('gb2312'))
    return m.hexdigest()


def parse_data(result: dict):
    original_content = content = result['content']
    status = True
    for itemResult in result['results']:
        if itemResult['suggestion'] == 'block':
            for itemDetail in itemResult['details']:
                if 'contexts' in itemDetail:
                    for itemContext in itemDetail["contexts"]:
                        content = re.sub(itemContext['context'], "<吃掉了>", content, flags=re.I)
                        status = False
                else:
                    content = "<全部吃掉了>"
                    status = False
    return {'content': content, 'status': status, 'original': original_content}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(*text) -> list:
    '''检查字符串是否合规

    :param text: 字符串（List/Union）。
    :returns: 经过审核后的字符串。不合规部分会被替换为'<吃掉了>'，全部不合规则是'<全部吃掉了>'，结构为[{'审核后的字符串': 处理结果（True/False，默认为True）}]
    '''
    access_key_id = Config("check_accessKeyId")
    access_key_secret = Config("check_accessKeySecret")
    text = list(text)
    if not access_key_id or not access_key_secret or not EnableDirtyWordCheck.status:
        Logger.warn('Dirty words filter was disabled, skip.')
        query_list = []
        for t in text:
            query_list.append({'content': t, 'status': True, 'original': t})
        return query_list
    if not text:
        return []
    query_list = {}
    count = 0
    for t in text:
        if t == '':
            query_list.update({count: {t: {'content': t, 'status': True, 'original': t}}})
        else:
            query_list.update({count: {t: False}})
        count += 1
    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                cache = DirtyWordCache(pq)
                if not cache.need_insert:
                    query_list.update({q: {pq: parse_data(cache.get())}})
    call_api_list = {}
    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                if pq not in call_api_list:
                    call_api_list.update({pq: []})
                call_api_list[pq].append(q)
    call_api_list_ = [x for x in call_api_list]
    Logger.debug(call_api_list_)
    if call_api_list_:
        body = {
            "scenes": [
                "antispam"
            ],
            "tasks": list(map(lambda x: {
                "dataId": "Nullcat is god {}".format(time.time()),
                "content": x
            }, call_api_list_))
        }
        client_info = '{}'
        root = 'https://green.cn-shanghai.aliyuncs.com'
        url = '/green/text/scan?{}'.format(client_info)

        gmt_format = '%a, %d %b %Y %H:%M:%S GMT'
        date = datetime.datetime.utcnow().strftime(gmt_format)
        nonce = 'LittleC sb {}'.format(time.time())
        content_md5 = base64.b64encode(hashlib.md5(json.dumps(body).encode('utf-8')).digest()).decode('utf-8')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Content-MD5': content_md5,
            'Date': date,
            'x-acs-version': '2018-05-09',
            'x-acs-signature-nonce': nonce,
            'x-acs-signature-version': '1.0',
            'x-acs-signature-method': 'HMAC-SHA1'
        }
        tmp = {
            'x-acs-version': '2018-05-09',
            'x-acs-signature-nonce': nonce,
            'x-acs-signature-version': '1.0',
            'x-acs-signature-method': 'HMAC-SHA1'
        }
        sorted_header = {k: tmp[k] for k in sorted(tmp)}
        step1 = '\n'.join(list(map(lambda x: "{}:{}".format(x, sorted_header[x]), list(sorted_header.keys()))))
        step2 = url
        step3 = "POST\napplication/json\n{contentMd5}\napplication/json\n{date}\n{step1}\n{step2}".format(
            contentMd5=content_md5,
            date=headers['Date'], step1=step1, step2=step2)
        sign = "acs {}:{}".format(access_key_id, hash_hmac(access_key_secret, step3, hashlib.sha1))
        headers['Authorization'] = sign
        # 'Authorization': "acs {}:{}".format(accessKeyId, sign)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post('{}{}'.format(root, url), data=json.dumps(body)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    Logger.debug(result)
                    for item in result['data']:
                        content = item['content']
                        for n in call_api_list[content]:
                            query_list.update({n: {content: parse_data(item)}})
                        DirtyWordCache(content).update(item)
                else:
                    raise ValueError(await resp.text())
    results = []
    Logger.debug(query_list)
    for x in query_list:
        for y in query_list[x]:
            results.append(query_list[x][y])
    return results


async def check_bool(*text):
    chk = await check(*text)
    for x in chk:
        if not x['status']:
            return True
    return False


def rickroll(msg):
    if Config("enable_rickroll") and Config("rickroll_url"):
        return Config("rickroll_url")
    else:
        return msg.locale.t("error.message.chain.unsafe")
