from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.constants.exceptions import NoReportException
from core.types import Param

echo = module("echo", required_superuser=True, base=True, doc=True)


@echo.command()
async def _(msg: Bot.MessageSession):
    dis = await msg.wait_next_message(I18NContext("core.message.echo.prompt"), delete=True, append_instruction=False)
    if dis:
        try:
            dis = dis.as_display()
            await msg.finish(Plain(dis, allow_parse=False))
        except Exception as e:
            raise NoReportException(str(e))


@echo.command("[<display_msg>] {{I18N:core.help.echo}}")
async def _(msg: Bot.MessageSession, dis: Param("<display_msg>", str)):
    try:
        await msg.finish(Plain(dis, allow_parse=False))
    except Exception as e:
        raise NoReportException(str(e))
