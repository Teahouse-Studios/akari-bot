from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module

leave = module(
    "leave",
    alias="dismiss",
    base=True,
    doc=True,
    required_admin=True,
    available_for=["QQ|Group"],
)


@leave.command("{{I18N:core.help.leave}}")
async def _(msg: Bot.MessageSession):
    if await msg.wait_confirm(I18NContext("core.message.leave.confirm")):
        await msg.send_message(I18NContext("core.message.leave.success"))
        await msg.call_onebot_api("set_group_leave", group_id=int(msg.session_info.get_common_target_id()))
    else:
        await msg.finish()
