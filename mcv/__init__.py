import requests
import json
import asyncio
import re
async def mcv():
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    try:
        version_manifest = requests.get(url)
        file = json.loads(version_manifest.text)
        return("最新版：" + file['latest']['release'] + "，最新快照：" + file['latest']['snapshot'])
    except Exception:
        return("发生错误：土豆熟了。")

async def mcbv():
    url = 'https://bugs.mojang.com/rest/api/2/project/10200/versions'
    q = requests.get(url)
    w = json.loads(q.text)
    f = []
    z = []
    for x in w[:]:
        if x['archived'] == False:
            try:
                e = re.match(r'(.*)Beta$',x['name'])
                f.append(e.group(1))
            except Exception:
                z.append(x['name'])
        else:
            pass
    h = '| '
    d = h.join(f)
    u = h.join(z)
    return('Beta: '+str(d)+'\nRelease: '+u+'\n（数据来源于MoJira，可能会比官方发布要早一段时间。信息仅供参考。）')

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