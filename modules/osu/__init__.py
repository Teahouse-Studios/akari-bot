from core.builtins import Bot
from core.component import module

osu = module('osu', developers=['DoroWolf'], desc='{osu.help.desc}')

@osu.handle('bind <username> {{osu.help.bind}}')
async def _(msg: Bot.MessageSession, username: str):
    code: str = username.lower()
    getcode = await get_profile_name(code)
    if getcode:
        bind = OsuBindInfoManager(msg).set_bind_info(username=getcode[0])
        if bind:
            if getcode[1]:
                m = f'{getcode[1]}({getcode[0]})'
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
