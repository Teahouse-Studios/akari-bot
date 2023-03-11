from core.builtins import Bot,Image
from core.component import on_command
import requests

w = on_command('whois', desc='查询 IP Whois 信息',
               developers=['haoye_qwq'])


@w.handle('<domain>')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<domain>']
    url = 'https://v.api.aa1.cn/api/whois/index.php?domain=' + query
    response = requests.get(url)
    if(response.status_code == 200):
        content = response.text
        send = 'https://api.setbug.com/tools/text2image/?text=' + content
        await msg.sendMessage(Image(send))
    else:
        await msg.sendMessage('请求失败')
    