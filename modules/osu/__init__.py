from config import Config
from core.builtins import Bot
from core.component import module
from core.exceptions import ConfigValueError
from .dbutils import OsuBindInfoManager
from .utils import get_profile_name

osu = module('osu', developers=['DoroWolf'], desc='{osu.help.desc}')

@osu.handle('bind <username> {{osu.help.bind}}')
async def _(msg: Bot.MessageSession, username: str):
    if not Config('osu_api_key', cfg_type=str):
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))
    code: str = username.lower()
    getcode = await get_profile_name(code)
    if getcode:
        bind = OsuBindInfoManager(msg).set_bind_info(username=getcode[0])
        if bind:
            m = f'{getcode[1]}({getcode[0]})'
            await msg.finish(msg.locale.t('osu.message.bind.success') + m)
    else:
        await msg.finish(msg.locale.t('osu.message.bind.failed'))


@osu.handle('unbind {{osu.help.unbind}}')
async def _(msg: Bot.MessageSession):
    if not Config('osu_api_key', cfg_type=str):
        raise ConfigValueError(msg.locale.t('error.config.secret.not_found'))
    unbind = OsuBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t('osu.message.unbind.success'))
