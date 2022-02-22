from core.component import on_command
from core.elements import MessageSession

from .moddetails import moddetails as m

moddetails = on_command(
    bind_prefix='moddetails',
    desc='从 MCMOD 获取 Minecraft Mod 内容的有关资料',
    developers=['Dianliang233', 'HornCopper', 'DrLee_lihr'],
)


@moddetails.handle('<content> {通过 Mod 内容的名称获取模组简介及链接，可使用物品/方块/实体的 ID 或准确中文。}')
async def main(msg: MessageSession):
    message = await m(msg.parsed_msg['<content>'])
    await msg.sendMessage(message)
