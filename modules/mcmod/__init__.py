from core.builtins import Bot
from core.component import on_command
from .mcmod import mcmod as m

mcmod = on_command(
    bind_prefix='mcmod',
    desc='从 MCMOD 获取 Minecraft Mod 信息',
    developers=['Dianliang233', 'HornCopper', 'DrLee_lihr'],
    alias={'moddetails': 'mcmod details'}
)


@mcmod.handle('<mod_name> {通过模组名获取模组简介及链接，可使用无歧义简写和准确中文。}')
async def main(msg: Bot.MessageSession):
    message = await m(msg.parsed_msg['<mod_name>'])
    await msg.finish(message)


@mcmod.handle('details <content> {通过 Mod 内容的名称获取模组简介及链接，可使用物品/方块/实体的 ID 或准确中文。}')
async def main(msg: Bot.MessageSession):
    message = await m(msg.parsed_msg['<content>'], detail=True)
    await msg.finish(message)
