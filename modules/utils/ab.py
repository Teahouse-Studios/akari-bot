import aiohttp
import ujson as json

from core.dirty_check import check
from modules.utils.UTC8 import UTC8
from modules.wiki.wikilib import wikilib


async def ab(wiki_url):
    if wiki_url:
        pageurl = await wikilib().get_article_path(wiki_url) + 'Special:AbuseLog'
        url = wiki_url + '?action=query&list=abuselog&aflprop=user|title|action|result|filter|timestamp&format=json'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                if req.status != 200:
                    return f"请求时发生错误：{req.status}\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title="
                else:
                    text1 = await req.text()
        file = json.loads(text1)
        d = []
        for x in file['query']['abuselog'][:5]:
            d.append('•' + x['title'] + ' - ' + x['user'] + '于' + UTC8(x['timestamp'], 'onlytimenoutc') + '\n过滤器名：' + x[
                'filter'] + '\n处理结果：' + x['result'])
        y = await check(*d)
        y = '\n'.join(y)
        if y.find('<吃掉了>') != -1 or y.find('<全部吃掉了>') != -1:
            return f'{pageurl}\n{y}\n...仅显示前5条内容\n检测到外来信息介入，请前往滥用日志查看所有消息。'
        else:
            return f'{pageurl}\n{y}\n...仅显示前5条内容'
    else:
        return '未设定起始Wiki。'
