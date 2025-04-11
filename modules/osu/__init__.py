from core.builtins import Bot
from core.component import module
from core.config import Config
from modules.osu.database.models import OsuBindInfo
from .profile import osu_profile
from .utils import get_profile_name

api_key = Config("osu_api_key", cfg_type=str, secret=True, table_name="module_osu")

osu = module("osu", developers=["DoroWolf"], desc="{osu.help.desc}", doc=True)


@osu.command(
    "profile [<username>] [-t <mode>] {{osu.help.profile}}",
    options_desc={"-t": "{osu.help.option.t}"},
)
async def _(msg: Bot.MessageSession, username: str = None):
    if username:
        query_id = username.lower()
    else:
        bind_info = await OsuBindInfo.get_or_none(sender_id=msg.target.sender_id)
        if not bind_info:
            await msg.finish(
                msg.locale.t("osu.message.user_unbound", prefix=msg.prefixes[0])
            )
        query_id = bind_info.username
    get_mode = msg.parsed_msg.get("-t", False)
    mode = get_mode["<mode>"] if get_mode else "0"
    await osu_profile(msg, query_id, mode, api_key)


@osu.command("bind <username> {{osu.help.bind}}")
async def _(msg: Bot.MessageSession, username: str):
    code: str = username.lower()
    getcode = await get_profile_name(msg, code, api_key)
    if getcode:
        await OsuBindInfo.set_bind_info(sender_id=msg.target.sender_id, username=getcode[0])
        if getcode[1]:
            m = f"{getcode[1]}{msg.locale.t("message.brackets", msg=getcode[0])}"
        else:
            m = getcode[0]
        await msg.finish(msg.locale.t("osu.message.bind.success") + m)
    else:
        await msg.finish(msg.locale.t("osu.message.bind.failed"))


@osu.command("unbind {{osu.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await OsuBindInfo.remove_bind_info(msg.target.sender_id)
    await msg.finish(msg.locale.t("osu.message.unbind.success"))
