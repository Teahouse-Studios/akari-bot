from core.elements import MessageSession
from core.component import on_command
from modules.utils.ab import ab
from modules.utils.newbie import newbie
from modules.utils.rc import rc
from modules.utils.ab_qq import ab_qq
from modules.utils.rc_qq import rc_qq
from modules.wiki.dbutils import WikiTargetInfo


def get_start_wiki(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    return start_wiki


r = on_command('rc', desc='获取默认wiki的最近更改', developers=['OasisAkari'])


@r.handle()
async def rc_loader(msg: MessageSession):
    start_wiki = get_start_wiki(msg)
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        nodelist = await rc_qq(start_wiki)
        await msg.fake_forward_msg(nodelist)
    else:
        res = await rc(start_wiki)
        await msg.sendMessage(res)


a = on_command('ab', desc='获取默认wiki的最近滥用日志', developers=['OasisAkari'])


@a.handle()
async def ab_loader(msg: MessageSession):
    start_wiki = get_start_wiki(msg)
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        nodelist = await ab_qq(start_wiki)
        await msg.fake_forward_msg(nodelist)
    else:
        res = await ab(start_wiki)
        await msg.sendMessage(res)


n = on_command('newbie', desc='获取默认wiki的新用户', developers=['OasisAkari'])


@n.handle()
async def newbie_loader(msg: MessageSession):
    res = await newbie(get_start_wiki(msg))
    await msg.sendMessage(res)
