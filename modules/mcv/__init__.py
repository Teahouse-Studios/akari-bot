from core.elements import MessageSession
from core.decorator import on_command
from .mcv import mcv, mcbv, mcdv


@on_command(
    bind_prefix='mcv',
    help_doc='~mcv {查询当前Minecraft Java版启动器内最新版本。}',
    alias='m',
    developers=['OasisAkari', 'Dianliang233'],
    recommend_modules='mcbv')
async def mcv_loader(msg: MessageSession):
    await msg.sendMessage(await mcv())


@on_command(
    bind_prefix='mcbv',
    help_doc='~mcbv {查询当前Minecraft 基岩版Jira内记录的最新版本。}',
    developers=['OasisAkari', 'Dianliang233'])
async def mcbv_loader(msg: MessageSession):
    await msg.sendMessage(await mcbv())


@on_command(
    bind_prefix='mcdv',
    help_doc='~mcdv {查询当前Minecraft Dungeons Jira内记录的最新版本。}',
    developers=['OasisAkari', 'Dianliang233'])
async def mcdv_loader(msg: MessageSession):
    await msg.sendMessage(await mcdv())
