from core.elements import MessageSession
from core.component import on_command
from .mcv import mcv, mcbv, mcdv

m = on_command(
    bind_prefix='mcv',
    desc='查询当前Minecraft Java版启动器内最新版本。',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules='mcbv')


@m.handle()
async def mcv_loader(msg: MessageSession):
    await msg.sendMessage(await mcv())


mb = on_command(
    bind_prefix='mcbv',
    desc='查询当前Minecraft 基岩版Jira内记录的最新版本。',
    developers=['OasisAkari', 'Dianliang233'])


@mb.handle()
async def mcbv_loader(msg: MessageSession):
    await msg.sendMessage(await mcbv())


md = on_command(
    bind_prefix='mcdv',
    desc='查询当前Minecraft Dungeons Jira内记录的最新版本。',
    developers=['OasisAkari', 'Dianliang233'])


@md.handle()
async def mcdv_loader(msg: MessageSession):
    await msg.sendMessage(await mcdv())
