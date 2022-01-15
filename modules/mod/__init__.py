import asyncio

from core.component import on_command, on_option
from core.dirty_check import check
from core.elements import MessageSession
from database import BotDBUtil

from .mod import mcmod as m

mcmod = on_command(
    bind_prefix='mod',
    desc='Minecraft Mod检索工具（使用MCMOD，无API支持，）',
    alias='mcmod',
    developers=['HornCopper'],
    required_admin = False, 
    base = False,
    required_superuser = False
)

@mcmod.handle('<mod_name> {通过模组名获取模组简介及链接（与查Wiki类似，但无API支持），可使用无歧义简写和准确中文。}')
async def main(msg: MessageSession):
    message = await m(msg.parsed_msg["<mod_name>"])
    await msg.sendMessage(message)
