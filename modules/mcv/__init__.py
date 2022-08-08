from core.builtins.message import MessageSession
from core.component import on_command
from .mcv import mcv, mcbv, mcdv, mcev

m = on_command(
    bind_prefix='mcv',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules=['mcbv', 'mcdv'])


@m.handle('{查询当前Minecraft Java版启动器内最新版本。}')
async def mcv_loader(msg: MessageSession):
    await msg.finish(await mcv())


mb = on_command(
    bind_prefix='mcbv',
    developers=['OasisAkari', 'Dianliang233'])


@mb.handle('{查询当前Minecraft 基岩版Jira内记录的最新版本。}')
async def mcbv_loader(msg: MessageSession):
    await msg.finish(await mcbv())


md = on_command(
    bind_prefix='mcdv',
    developers=['OasisAkari', 'Dianliang233'])


@md.handle('{查询当前Minecraft Dungeons Jira内记录的最新版本。}')
async def mcdv_loader(msg: MessageSession):
    await msg.finish(await mcdv())


me = on_command(
    bind_prefix='mcev',
    developers=['OasisAkari', 'Dianliang233'])


@me.handle('{查询当前Minecraft教育版Windows版记录的最新版本。}')
async def mcev_loader(msg: MessageSession):
    await msg.finish(await mcev())
