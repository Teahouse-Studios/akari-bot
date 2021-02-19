import base64
import datetime
import hashlib
import hmac
import json
import os.path
import time

import aiohttp

from config import config


def hash_hmac(key, code, sha1):
    hmac_code = hmac.new(key.encode(), code.encode(), hashlib.sha1)
    return base64.b64encode(hmac_code.digest()).decode('utf-8')


def computeMD5hash(my_string):
    m = hashlib.md5()
    m.update(my_string.encode('gb2312'))
    return m.hexdigest()


async def check(*text):
    config_path = os.path.abspath('config/config.cfg')
    try:
        accessKeyId = config(config_path, "Check_accessKeyId")
        accessKeySecret = config(config_path, "Check_accessKeySecret")
    except (FileNotFoundError, IndexError):
        return '\n'.join(text)
    body = {
        "scenes": [
            "antispam"
        ],
        "tasks": list(map(lambda x: {
            "dataId": "OasisAkari is god {}".format(time.time()),
            "content": x
        }, text))
    }
    clientInfo = '{}'
    root = 'https://green.cn-shanghai.aliyuncs.com'
    url = '/green/text/scan?{}'.format(clientInfo)

    GMT_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
    date = datetime.datetime.utcnow().strftime(GMT_FORMAT)
    nonce = 'OasisAkari is god forever {}'.format(time.time())
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
                resultUsers = []
                for item in result['data']:
                    content = item['content']
                    for itemResult in item['results']:
                        if itemResult['suggestion'] == 'block':
                            for itemDetail in itemResult['details']:
                                if 'contexts' in itemDetail:
                                    for itemContext in itemDetail["contexts"]:
                                        content = content.replace(itemContext['context'], '<吃掉了>')
                                else:
                                    content = "<全部吃掉了>"
                    resultUsers.append(content)
                return ''.join(resultUsers)

            else:
                return await resp.text()
