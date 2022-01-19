from core.component import on_command
from core.elements import MessageSession, Image

from .news import news as n

news = on_command(
    bind_prefix='news',
    desc='获取今日世界新闻。',
    developers=['HornCopper'])

@news.handle()
async def main(msg: MessageSession):
    img_url = await n()
    await msg.sendMessage([Image(path=img_url)])
