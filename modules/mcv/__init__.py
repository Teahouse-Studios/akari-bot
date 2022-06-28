from core.component import on_command
from core.builtins.message import MessageSession
from .mcv import mcv, mcbv, mcdv, mcev

m = on_command(
    bind_prefix='mcv',
    desc='查询当前Minecraft Java版启动器内最新版本。',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcbv', 'mcdv'])


@m.handle()
async def mcv_loader(msg: MessageSession):
    await msg.finish(await mcv())


mb = on_command(
    bind_prefix='mcbv',
    desc='查询当前Minecraft 基岩版Jira内记录的最新版本。',
    developers=['OasisAkari', 'Dianliang233'])


@mb.handle()
async def mcbv_loader(msg: MessageSession):
    await msg.finish(await mcbv())


md = on_command(
    bind_prefix='mcdv',
    desc='查询当前Minecraft Dungeons Jira内记录的最新版本。',
    developers=['OasisAkari', 'Dianliang233'])


@md.handle()
async def mcdv_loader(msg: MessageSession):
    await msg.finish(await mcdv())


me = on_command(
    bind_prefix='mcev',
    desc='查询当前Minecraft教育版Windows版记录的最新版本。',
    developers=['OasisAkari', 'Dianliang233'])


@me.handle()
async def mcev_loader(msg: MessageSession):
    await msg.finish(await mcev())
