from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Image
from database import BotDBUtil
from .dbutils import CytoidBindInfoManager
from .profile import cytoid_profile
from .rating import get_rating
from .utils import get_profile_name

cytoid = on_command('cytoid',
                    developers=['OasisAkari'], alias='ctd')


@cytoid.handle('profile [<UserID>] {查询一个用户的基本信息}')
async def _(msg: MessageSession):
    if msg.parsed_msg['profile']:
        await cytoid_profile(msg)


@cytoid.handle('(b30|r30) [<UserID>] {查询一个用户的b30/r30记录}')
async def _(msg: MessageSession):
    if 'b30' in msg.parsed_msg:
        query = 'b30'
    elif 'r30' in msg.parsed_msg:
        query = 'r30'
    else:
        query = False
    pat = msg.parsed_msg.get('<UserID>', False)
    if pat:
        query_id = pat
    else:
        query_id = CytoidBindInfoManager(msg).get_bind_username()
        if query_id is None:
            await msg.finish('未绑定用户，请使用~cytoid bind <username>绑定一个用户。')
    if query:
        if msg.target.targetFrom == 'TEST|Console':
            c = 0
        else:
            qc = BotDBUtil.CoolDown(msg, 'cytoid_rank')
            c = qc.check(150)
        if c == 0:
            img = await get_rating(query_id, query)
            if 'path' in img:
                await msg.sendMessage([Image(path=img['path'])], allow_split_image=False)
            if 'text' in img:
                await msg.sendMessage(img['text'])
            if msg.target.targetFrom != 'TEST|Console':
                if img['status']:
                    qc.reset()
        else:
            await msg.sendMessage(f'距离上次执行已过去{int(c)}秒，本命令的冷却时间为150秒。（据官方人员所述，此API的调用十分昂贵，故手动做出这一限制，请谅解。）')


@cytoid.handle('bind <username> {绑定一个Cytoid用户}')
async def _(msg: MessageSession):
    code: str = msg.parsed_msg['<username>']
    getcode = await get_profile_name(code)
    if getcode:
        bind = CytoidBindInfoManager(msg).set_bind_info(username=getcode[0])
        if bind:
            if getcode[1]:
                m = f'{getcode[1]}({getcode[0]})'
            else:
                m = getcode[0]
            await msg.finish(f'绑定成功：' + m)
    else:
        await msg.finish('绑定失败，请检查输入。')


@cytoid.handle('unbind {取消绑定用户}')
async def _(msg: MessageSession):
    unbind = CytoidBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish('取消绑定成功。')
    else:
        await msg.finish('未绑定用户。')
