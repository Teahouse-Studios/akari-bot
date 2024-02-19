from core.builtins import Bot
from core.component import module
from .mcv import mcv, mcbv, mcdv, mcev, mclgv

m = module('mcv',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcbv'])


@m.command('{{mcv.help.mcv}}')
async def mcv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcv(msg))


mb = module('mcbv',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcv'])


@mb.command('{{mcv.help.mcbv}}')
async def mcbv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcbv(msg))


md = module('mcdv',
    developers=['OasisAkari', 'Dianliang233'],
    hide=True)


@md.command('{{mcv.help.mcdv}}')
async def mcdv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcdv(msg))


me = module('mcev',
    developers=['OasisAkari', 'Dianliang233'],
    hide=True)


@me.command('{{mcv.help.mcev}}')
async def mcev_loader(msg: Bot.MessageSession):
    await msg.finish(await mcev(msg))


mlg = module('mclgv',
    developers=['OasisAkari', 'Dianliang233'],
    hide=True)


@mlg.command('{{mcv.help.mclgv}}')
async def mclgv_loader(msg: Bot.MessageSession):
    await msg.finish(await mclgv(msg))
