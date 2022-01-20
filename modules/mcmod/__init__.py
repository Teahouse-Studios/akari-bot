from core.component import on_command
from core.elements import MessageSession

from .mcmod import mcmod as m

mcmod = on_command(
    bind_prefix='mcmod',
    desc='从 MCMOD 获取 Minecraft Mod 信息',
    developers=['Dianliang233', 'HornCopper'],
)


@mcmod.handle('<mod_name> {通过模组名获取模组简介及链接，可使用无歧义简写和准确中文。}')
async def main(msg: MessageSession):
    message = await m(msg.parsed_msg['<mod_name>'])
    await msg.sendMessage(message)
