from core.elements import MessageSession, Image
from core.decorator import on_command
from database import BotDBUtil
from .profile import cytoid_profile
from .rating import get_rating


@on_command('cytoid', help_doc=('~cytoid (b30|r30) <UserID> {查询一个用户的b30/r30记录}',
                             '~cytoid profile <UserID> {查询一个用户的基本信息}'),
            developers=['OasisAkari'],
            allowed_none=False)
async def cytoid(msg: MessageSession):
    if msg.parsed_msg['profile']:
        await cytoid_profile(msg)
    if msg.parsed_msg['b30']:
        query = 'b30'
    elif msg.parsed_msg['r30']:
        query = 'r30'
    else:
        query = False
    if query:
        qc = BotDBUtil.CoolDown(msg, 'cytoid_rank')
        c = qc.check(300)
        if c == 0:
            img = await get_rating(msg.parsed_msg['<UserID>'], query)
            if 'path' in img:
                await msg.sendMessage([Image(path=img['path'])])
            if 'text' in img:
                await msg.sendMessage(img['text'])
            if img['status']:
                qc.reset()
        else:
            await msg.sendMessage(f'距离上次执行已过去{int(c)}秒，本命令的冷却时间为300秒。')
