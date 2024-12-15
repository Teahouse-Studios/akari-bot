from core.builtins import Bot, Image
from core.component import module
from core.utils.cooldown import CoolDown
from .dbutils import CytoidBindInfoManager
from .profile import cytoid_profile
from .rating import get_rating
from .utils import get_profile_name

ctd = module(
    "cytoid",
    desc="{cytoid.help.desc}",
    doc=True,
    developers=["OasisAkari"],
    alias="ctd",
)


@ctd.handle("profile [<username>] {{cytoid.help.profile}}")
async def _(msg: Bot.MessageSession, username: str = None):
    await cytoid_profile(msg, username)


@ctd.handle(
    "b30 [<username>] {{cytoid.help.b30}}", "r30 [<username>] {{cytoid.help.r30}}"
)
async def _(msg: Bot.MessageSession, username: str = None):
    if "b30" in msg.parsed_msg:
        query = "b30"
    elif "r30" in msg.parsed_msg:
        query = "r30"
    else:
        return
    if username:
        query_id = username
    else:
        query_id = CytoidBindInfoManager(msg).get_bind_username()
        if not query_id:
            await msg.finish(
                msg.locale.t("cytoid.message.user_unbound", prefix=msg.prefixes[0])
            )
    if query:
        if msg.target.client_name == "TEST":
            c = 0
        else:
            qc = CoolDown("cytoid_rank", msg)
            c = qc.check(150)
        if c == 0:
            img = await get_rating(msg, query_id, query)
            if msg.target.client_name != "TEST" and img["status"]:
                qc.reset()
            if "path" in img:
                await msg.finish([Image(path=img["path"])], enable_split_image=False)
            elif "text" in img:
                await msg.finish(img["text"])
        else:
            res = msg.locale.t("message.cooldown", time=int(150 - c)) + msg.locale.t(
                "cytoid.message.b30.cooldown"
            )
            await msg.finish(res)


@ctd.handle("bind <username> {{cytoid.help.bind}}")
async def _(msg: Bot.MessageSession, username: str):
    code: str = username.lower()
    getcode = await get_profile_name(code)
    if getcode:
        bind = CytoidBindInfoManager(msg).set_bind_info(username=getcode[0])
        if bind:
            if getcode[1]:
                m = f"{getcode[1]}({getcode[0]})"
            else:
                m = getcode[0]
            await msg.finish(msg.locale.t("cytoid.message.bind.success") + m)
    else:
        await msg.finish(msg.locale.t("cytoid.message.bind.failed"))


@ctd.handle("unbind {{cytoid.help.unbind}}")
async def _(msg: Bot.MessageSession):
    unbind = CytoidBindInfoManager(msg).remove_bind_info()
    if unbind:
        await msg.finish(msg.locale.t("cytoid.message.unbind.success"))
