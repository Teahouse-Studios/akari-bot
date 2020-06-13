import json
import requests
import re
async def mcdv():
    url = 'https://bugs.mojang.com/rest/api/2/project/11901/versions'
    q = requests.get(url)
    w = json.loads(q.text)
    f = []
    for x in w[:]:
        if x['archived'] == False:
            s = x['name']
        else:
            pass
    return('最新版：'+s+'\n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）')