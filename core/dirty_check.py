import base64
import datetime
import hashlib
import hmac
import json
import time

import aiohttp
from tenacity import retry, wait_fixed, stop_after_attempt
from core.elements import EnableDirtyWordCheck
from core.logger import Logger
from database.logging_message import DirtyWordCache

from config import Config


def hash_hmac(key, code, sha1):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode('utf-8')


def computeMD5hash(my_string):
    m = hashlib.md5()
    m.update(my_string.encode('gb2312'))
    return m.hexdigest()


def parse_data(result: dict):
    original_content = content = result['content']
    for itemResult in result['results']:
        if itemResult['suggestion'] == 'block':
            for itemDetail in itemResult['details']:
                if 'contexts' in itemDetail:
                    for itemContext in itemDetail["contexts"]:
                        content = content.replace(itemContext['context'], '<吃掉了>')
                else:
                    content = "<全部吃掉了>"
    return {original_content: content}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def check(*text) -> list:
    accessKeyId = Config("Check_accessKeyId")
    accessKeySecret = Config("Check_accessKeySecret")
    if not accessKeyId or not accessKeySecret or not EnableDirtyWordCheck.status:
        Logger.warn('Dirty words filter was disabled, skip.')
        return list(text)
    query_list = {}
    count = 0
    for t in text:
        query_list.update({count: {t: False}})
        count += 1
    for q in query_list:
        for pq in query_list[q]:
            cache = DirtyWordCache(pq)
            if not cache.need_insert:
                query_list.update({q: parse_data(cache.get())})
    call_api_list = {}
    for q in query_list:
        for pq in query_list[q]:
            if not query_list[q][pq]:
                call_api_list.update({pq: q})
    call_api_list_ = [x for x in call_api_list]
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
        clientInfo = '{}'
        root = 'https://green.cn-shanghai.aliyuncs.com'
        url = '/green/text/scan?{}'.format(clientInfo)

        GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
        date = datetime.datetime.utcnow().strftime(GMT_FORMAT)
        nonce = 'LittleC is god forever {}'.format(time.time())
        contentMd5 = base64.b64encode(hashlib.md5(json.dumps(body).encode('utf-8')).digest()).decode('utf-8')
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Content-MD5': contentMd5,
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
            contentMd5=contentMd5,
            date=headers['Date'], step1=step1, step2=step2)
        sign = "acs {}:{}".format(accessKeyId, hash_hmac(accessKeySecret, step3, hashlib.sha1))
        headers['Authorization'] = sign
        # 'Authorization': "acs {}:{}".format(accessKeyId, sign)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post('{}{}'.format(root, url), data=json.dumps(body)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(result)
                    for item in result['data']:
                        content = item['content']
                        query_list.update({call_api_list[content]: parse_data(item)})
                        DirtyWordCache(content).update(item)
                else:
                    raise ValueError(await resp.text())
    results = []
    for x in query_list:
        for y in query_list[x]:
            results.append(y)
    return results


