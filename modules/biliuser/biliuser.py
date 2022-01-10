from core.component import on_command, on_option
from core.dirty_check import check
from core.elements import MessageSession
from database import BotDBUtil
from .biliuser import handle_uid as biliuser

biliuser = on_command(
    bind_prefix='biliuser',
    desc='根据UID获取B站用户头像、简介和会员信息。',
    alias='bu',
    developers=['HornCopper'],
    required_admin = False,
    base = False,
    required_superuser = False
)

@biliuser.handle(['<Bili_UID> - 获取哔哩哔哩用户信息（使用UID）。'])
async def main(uid: MessageSession):
    await biliuser(uid)
