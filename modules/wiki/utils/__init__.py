import traceback

from core.builtins.message import MessageSession
from core.component import on_command
from modules.wiki.utils.dbutils import WikiTargetInfo, Audit
from modules.wiki.utils.wikilib import WikiLib, WhatAreUDoingError, PageInfo, InvalidWikiError, QueryInfo
from .ab import ab
from .ab_qq import ab_qq
from .newbie import newbie
from .rc import rc
from .rc_qq import rc_qq

rc_ = on_command('rc', desc='获取默认wiki的最近更改', developers=['OasisAkari'])


@rc_.handle()
async def rc_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await rc_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.finish('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await rc(start_wiki)
        await msg.finish(res)


a = on_command('ab', desc='获取默认wiki的最近滥用日志', developers=['OasisAkari'])


@a.handle()
async def ab_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    legacy = True
    if msg.Feature.forward and msg.target.targetFrom == 'QQ|Group':
        try:
            nodelist = await ab_qq(start_wiki)
            await msg.fake_forward_msg(nodelist)
            legacy = False
        except Exception:
            traceback.print_exc()
            await msg.finish('无法发送转发消息，已自动回滚至传统样式。')
            legacy = True
    if legacy:
        res = await ab(start_wiki)
        await msg.finish(res)


n = on_command('newbie', desc='获取默认wiki的新用户', developers=['OasisAkari'])


@n.handle()
async def newbie_loader(msg: MessageSession):
    start_wiki = WikiTargetInfo(msg).get_start_wiki()
    if start_wiki is None:
        return await msg.finish('未设置起始wiki。')
    res = await newbie(start_wiki)
    await msg.finish(res)
