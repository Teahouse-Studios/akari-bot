from core.builtins import Bot
from core.component import on_command
import requests
import json

hit = on_command('hitokoto', alias={'一言': 'hitokoto',
                                        'hit': 'hitokoto',
                                        },
                desc='一言', developers=['haoye_qwq'])

@hit.handle()
async def rand_hit(msg:Bot.MessageSession):
    url = 'https://v1.hitokoto.cn/'
    response = requests.get(url)
    if(response.status_code == 200):
        content = response.text
        json_dict = json.loads(content)
        yee = json_dict.get('hitokoto')
        frm = json_dict.get('from')
        who = json_dict.get('from_who')
        await msg.sendMessage(f"[{yee}]\n    ——{who}《{frm}》")
    else:
        await msg.sendMessage('请求失败')