from core.decorator import command
from core.elements import MessageSession
from .mcv import mcv, mcbv, mcdv


@command(
    bind_prefix='mcv',
    help_doc='~mcv {查询当前Minecraft Java版启动器内最新版本。}',
    alias='m')
async def mcv_loader(msg: MessageSession):
    run = await mcv()
    await msg.sendMessage(run)
