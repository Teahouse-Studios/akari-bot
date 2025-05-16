from core.builtins import Bot, I18NContext, Image
from core.component import module
from core.utils.cooldown import CoolDown
from modules.cytoid.database.models import CytoidBindInfo
from .profile import cytoid_profile
from .rating import get_rating
from .utils import get_profile_name

ctd = module(
    "cytoid",
    desc="[I18N:cytoid.help.desc]",
    doc=True,
    developers=["OasisAkari"],
    alias="ctd",
)


@ctd.command("profile [<username>] {[I18N:cytoid.help.profile]}")
async def _(msg: Bot.MessageSession, username: str = None):
    await cytoid_profile(msg, username)


@ctd.command(
    "b30 [<username>] {[I18N:cytoid.help.b30]}",
    "r30 [<username>] {[I18N:cytoid.help.r30]}"
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
        bind_info = await CytoidBindInfo.get_by_sender_id(msg, create=False)
        if not bind_info:
            await msg.finish(I18NContext("cytoid.message.user_unbound", prefix=msg.prefixes[0]))
        query_id = bind_info.username
    if query:
        if msg.target.client_name == "TEST":
            c = 0
        else:
            qc = CoolDown("cytoid_rank", msg, 150)
            c = qc.check()
        if c == 0:
            img = await get_rating(msg, query_id, query)
            if msg.target.client_name != "TEST" and img["status"]:
                qc.reset()
            if "path" in img:
                await msg.finish([Image(path=img["path"])], enable_split_image=False)
            elif "text" in img:
                await msg.finish(img["text"])
        else:
            await msg.finish([I18NContext("message.cooldown", time=int(c)),
                              I18NContext("cytoid.message.b30.cooldown")])


@ctd.command("bind <username> {[I18N:cytoid.help.bind]}")
async def _(msg: Bot.MessageSession, username: str):
    code: str = username.lower()
    getcode = await get_profile_name(code)
    if getcode:
        await CytoidBindInfo.set_bind_info(msg.target.sender_id, getcode[0])
        if getcode[1]:
            m = f"{getcode[1]}({getcode[0]})"
        else:
            m = getcode[0]
        await msg.finish(I18NContext("cytoid.message.bind.success", user=m))
    else:
        await msg.finish(I18NContext("cytoid.message.bind.failed"))


@ctd.command("unbind {[I18N:cytoid.help.unbind]}")
async def _(msg: Bot.MessageSession):
    await CytoidBindInfo.remove_bind_info(msg.target.sender_id)
    await msg.finish(I18NContext("cytoid.message.unbind.success"))
