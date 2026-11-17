from core.builtins.bot import Bot
from core.builtins.message.mention import wrap_sender_id
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Button
from core.component import module
from core.constants.exceptions import NoReportException

say = module("say", required_superuser=True, base=True, doc=True)


@say.command("<display_msg> {{I18N:core.help.say}}")
async def _(msg: Bot.MessageSession, display_msg: str):
    try:
        display_msg = wrap_sender_id(display_msg, msg.session_info.sender_from)
        await msg.finish(display_msg, quote=False)
    except Exception as e:
        raise NoReportException(str(e))


@say.command("md <display_msg> {{I18N:core.help.say.md}}")
async def _(msg: Bot.MessageSession, display_msg: str):
    try:
        display_msg = wrap_sender_id(display_msg, msg.session_info.sender_from)
        chain = MessageChain.assign(display_msg)
        chain += Button("md test", "md test")
        await msg.finish(chain, quote=False)
    except Exception as e:
        raise NoReportException(str(e))
