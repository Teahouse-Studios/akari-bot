from core.builtins import Bot
from core.component import module
from .mcv import mcv, mcbv, mcdv, mcev

m = module(
    bind_prefix='mcv',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcbv', 'mcdv'])


@m.handle('{{mcv.mcv.help}}')
async def mcv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcv())


mb = module(
    bind_prefix='mcbv',
    developers=['OasisAkari', 'Dianliang233'])


@mb.handle('{{mcv.mcbv.help}}')
async def mcbv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcbv())


md = module(
    bind_prefix='mcdv',
    developers=['OasisAkari', 'Dianliang233'])


@md.handle('{{mcv.mcdv.help}}')
async def mcdv_loader(msg: Bot.MessageSession):
    await msg.finish(await mcdv())


me = module(
    bind_prefix='mcev',
    developers=['OasisAkari', 'Dianliang233'])


@me.handle('{{mcv.mcev.help}}')
async def mcev_loader(msg: Bot.MessageSession):
    await msg.finish(await mcev())
