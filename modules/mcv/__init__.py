from core.elements import MessageSession
from core.loader.decorator import command
from .mcv import mcv, mcbv, mcdv


@command(
    bind_prefix='mcv',
    help_doc='~mcv {查询当前Minecraft Java版启动器内最新版本。}',
    alias='m',
    recommend_modules='mcbv')
async def mcv_loader(msg: MessageSession):
    await msg.sendMessage(await mcv())


@command(
    bind_prefix='mcbv',
    help_doc='~mcbv {查询当前Minecraft 基岩版Jira内记录的最新版本。}')
async def mcbv_loader(msg: MessageSession):
    await msg.sendMessage(await mcbv())


@command(
    bind_prefix='mcdv',
    help_doc='~mcdv {查询当前Minecraft Dungeons Jira内记录的最新版本。}')
async def mcdv_loader(msg: MessageSession):
    await msg.sendMessage(await mcdv())
