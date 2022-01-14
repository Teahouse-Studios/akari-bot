import asyncio

from core.component import on_command, on_option
from core.dirty_check import check
from core.elements import MessageSession
from database import BotDBUtil
from .biliuser import biliuser as bu

biliuser = on_command(
    bind_prefix='biliuser',
    desc='根据UID获取哔哩哔哩用户信息。',
    alias='bu',
    developers=['HornCopper'],
    required_admin = False, 
    base = False,
    required_superuser = False
)
@biliuser.handle('<uid> {根据UID获取哔哩哔哩用户信息}')
async def main(msg: MessageSession):
    uid = f'{msg.parsed_msg["<uid>"]}'
    message = await bu(uid)
    await msg.sendMessage(message)
