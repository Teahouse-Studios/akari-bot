import traceback

from core.component import on_command
from core.builtins.message import MessageSession

from .mcbbs_news import get_news as news
from config import Config

mcbbs_news = on_command(
    bind_prefix='mcbbs_news',
    alias=['mn', 'mcbbsnews'],
    desc='获得 MCBBS 幻翼快讯版最新新闻',
    developers=['HornCopper', 'OasisAkari']
)


@mcbbs_news.handle()
async def main(msg: MessageSession):
    def template(sth):
        return {"type": "node", "data": {"name": f"MCBBS · 幻翼快讯", "uin": qq_account,
                                         "content": [{"type": "text", "data": {"text": sth}}]}}

    message = ""
    nodelist = []
    response = await news()
    titles = response["titles"]
    authors = response["authors"]
    time = response["time"]
    kinds = response["kinds"]
    links = response["links"]
    qq_account = Config("qq_account")
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            for i in range(len(titles)):
                nodelist.append(template(f"标题：{titles[i]}\n作者：{authors[i]}\n发布日期：{time[i]}\n链接：{links[i]}"))
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.finish('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:  # 长得过分，所以截取5条
        message = ""
        for i in range(5):
            message = message + f"{kinds[i]}{titles[i]} · {authors[i]}（{time[i]}）\n"
        await msg.sendMessage(message[0:-1])  # 最后会多一个换行符
