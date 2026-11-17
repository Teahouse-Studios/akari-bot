from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module

mute = module("mute", base=True, doc=True, required_admin=True)


@mute.command("{{I18N:core.help.mute}}")
async def _(msg: Bot.MessageSession):
    state = await msg.session_info.target_union_info.switch_mute()
    if state:
        await msg.finish(I18NContext("core.message.mute.enable"))
    else:
        await msg.finish(I18NContext("core.message.mute.disable"))
