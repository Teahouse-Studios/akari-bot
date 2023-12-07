from core.builtins import Bot
from core.component import module
from .mcv import mcv, mcbv, mcdv, mcev, mclgv

m = module(
    bind_prefix='mcv',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcbv', 'mcdv'])


@m.command('{{mcv.help.mcv}}')
async def mcv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcv(msg))


mb = module(
    bind_prefix='mcbv',
    developers=['OasisAkari', 'Dianliang233'])


@mb.command('{{mcv.help.mcbv}}')
async def mcbv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcbv(msg))


md = module(
    bind_prefix='mcdv',
    developers=['OasisAkari', 'Dianliang233'])


@md.command('{{mcv.help.mcdv}}')
async def mcdv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcdv(msg))


me = module(
    bind_prefix='mcev',
    developers=['OasisAkari', 'Dianliang233'])


@me.command('{{mcv.help.mcev}}')
async def mcev_loader(msg: Bot.MessageSession):
    await msg.finish(await mcev(msg))


mlg = module(
    bind_prefix='mclgv',
    developers=['OasisAkari', 'Dianliang233'])


@mlg.command('{{mcv.help.mclgv}}')
async def mclgv_loader(msg: Bot.MessageSession):
    await msg.finish(await mclgv(msg))