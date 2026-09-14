from core.builtins.bot import Bot
from core.component import module
from core.constants.exceptions import TestException

rse = module("raise", required_superuser=True, base=True, doc=True)


@rse.command("[<args>] {{I18N:core.help.raise}}")
async def _(msg: Bot.MessageSession, args: str | None = None):
    e = args or "{I18N:core.message.raise}"
    raise TestException(str(e))
