import re

import aiohttp
import time
from graia.application import MessageChain
from graia.application.message.elements.internal import At, Plain
from core.template import sendMessage
from config import Config
import random
import urllib.parse
from hashlib import md5

config = Config().config

nlp_appid = config('NLP_AppID')
nlp_appkey = config('NLP_AppKEY')
account = config('account')
nlp_url = 'https://api.ai.qq.com/fcgi-bin/nlp/nlp_textchat'


def getRandomSet(bits):
    num_set = [chr(i) for i in range(48,58)]
    char_set = [chr(i) for i in range(97,123)]
    total_set = num_set + char_set

    value_set = "".join(random.sample(total_set, bits))

    return value_set


def calculate_sign(data):
    lst = []
    for x in data:
        a = f'{x}={urllib.parse.quote(data[x])}'
        lst.append(a)
        print(a)
    lst.append(f'app_key={nlp_appkey}')
    z = '&'.join(lst).encode('utf8')
    print(z)
    return md5(z).hexdigest().upper()


async def ai_question(kwargs: dict):
    msg = kwargs[MessageChain]
    ats = msg.get(At)
    atme = False
    for at in ats:
        print(at)
        if at.target == int(account):
            atme = True
    print(atme)
    if atme:
        msglist = []
        msgs = msg.get(Plain)
        for msg in msgs:
            if msg.text != ' ':
                msglist.append(msg.text)
        if msglist:
            question = re.sub(r'^ ', '', '+'.join(msglist))
            question = re.sub(' ','+', question)
            nlp_data = {'app_id': nlp_appid,
                        'time_stamp': str(int(time.time())),
                        'nonce_str': getRandomSet(16),
                        'session': '10000',
                        'question': question}
            nlp_data = {k: nlp_data[k] for k in sorted(nlp_data)}
            sign = {'sign': calculate_sign(nlp_data)}
            print(sign)
            nlp_data.update(sign)
            print(nlp_data)

            async with aiohttp.ClientSession() as session:
                async with session.post(nlp_url, data=nlp_data) as resp:
                    print(await resp.read())
                    if hasattr(resp, 'json'):
                        msg = await getattr(resp, 'json')()
                    await sendMessage(kwargs, msg['data']['answer'])


regex = {'ai': ai_question}