from core.builtins import Bot
from core.component import on_command
import requests
# from .domain import check_domain, format_domain

w = on_command('whois', desc='查询 IP Whois 信息',
               developers=['haoye_qwq'])


@w.handle('<domain>')
async def _(msg: Bot.MessageSession):
    query = msg.parsed_msg['<ip_or_domain>']
    url = 'https://v.api.aa1.cn/api/whois/index.php?domain=' + query
    response = requests.get(url)
    if(response.status_code == 200):
        content = response.text
        await msg.sendMessage(content)
    else:
        await msg.sendMessage('请求失败')
    