import json
import requests
import re
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