from core.builtins import Bot
from core.component import on_command
import requests

hit = on_command('hitokoto', alias={'一言': 'hitokoto',
                                        'hit': 'hitokoto',
                                        },
                desc='一言', developers=['haoye_qwq'])

@hit.handle()
async def rand_hit(msg:Bot.MessageSession):
    url = 'https://v1.hitokoto.cn/?encode=text'
    response = requests.get(url)
    if(response.status_code == 200):
        content = response.text
        await msg.sendMessage(content)
    else:
        await msg.sendMessage('请求失败')