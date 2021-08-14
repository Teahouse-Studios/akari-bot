from core.elements import MessageSession
from core.loader.decorator import command
from modules.utils import ab, rc, newbie
from modules.wiki.dbutils import WikiTargetInfo


def get_start_wiki(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    return start_wiki


@command('rc', help_doc='~rc {获取默认wiki的最近更改}')
async def rc_loader(msg: MessageSession):
    res = await rc(get_start_wiki(msg))
    await msg.sendMessage(res)


@command('ab', help_doc='~ab {获取默认wiki的最近滥用日志}')
async def ab_loader(msg: MessageSession):
    res = await ab(get_start_wiki(msg))
    await msg.sendMessage(res)


@command('newbie', help_doc='~newbie {获取默认wiki的新用户}')
async def newbie_loader(msg: MessageSession):
    res = await newbie(get_start_wiki(msg))
    await msg.sendMessage(res)
