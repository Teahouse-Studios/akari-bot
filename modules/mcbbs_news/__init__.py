from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Url
from core.logger import Logger
from .mcbbs_news import news

mcbbs_news = on_command(
    bind_prefix='mcbbs_news',
    alias=['mn', 'mcbbsnews', 'mcbbs'],
    desc='获得 MCBBS 幻翼快讯版最新新闻（未被版主高亮过的新闻将被忽略）',
    developers=['Dianliang233']
)


@mcbbs_news.handle('{获得 MCBBS 幻翼快讯版最新新闻（未被版主高亮过的新闻将被忽略）}')
async def main(msg: MessageSession):
    res = await news()
    Logger.debug('res' + str(res))
    if res is None:
        message = '没有找到任何新闻。'
    else:
        lst = []
        for i in res:
            lst += [f'{i["count"]}. [{i["category"]}] {i["title"]} - {i["author"]} @ {i["time"]}\n{i["url"]}']
        message = '\n'.join(lst) + '\n更多资讯详见 ' + \
                  Url('https://www.mcbbs.net/forum-news-1.html').url
    await msg.finish(message)
