from core.builtins import Bot
from core.component import module
from .dbutils import OsuBindInfoManager
from .profile import osu_profile
from .utils import get_profile_name

osu = module('osu', developers=['DoroWolf'], desc='{osu.help.desc}')


@osu.handle('profile [<username>] [-t <mode>] {{osu.help.profile}}',
             options_desc={'-t': '{osu.help.option.t}'})
async def _(msg: Bot.MessageSession, username: str = None):
    if username:
        query_id = username.lower()
    else:
        query_id = OsuBindInfoManager(msg).get_bind_username()
        if not query_id:
            await msg.finish(msg.locale.t('osu.message.user_unbound', prefix=msg.prefixes[0]))
    get_mode = msg.parsed_msg.get('-t', False)
    mode = get_mode['<mode>'] if get_mode else '0'
    await osu_profile(msg, query_id, mode)


@osu.handle('bind <username> {{osu.help.bind}}')
async def _(msg: Bot.MessageSession, username: str):
    code: str = username.lower()
    getcode = await get_profile_name(msg, code)
    if getcode:
        bind = OsuBindInfoManager(msg).set_bind_info(username=getcode[0])
        if bind:
            if getcode[1]:
                m = f"{getcode[1]}{msg.locale.t('message.brackets', msg=getcode[0])}"
            else:
                m = getcode[0]
        await msg.finish(msg.locale.t('osu.message.bind.success') + m)
    else:
        await msg.finish(msg.locale.t('osu.message.bind.failed'))


@osu.handle('unbind {{osu.help.unbind}}')
async def _(msg: Bot.MessageSession):
    unbind = OsuBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t('osu.message.unbind.success'))
