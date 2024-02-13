import sys

from core.builtins import Bot
from core.component import module

exit = module('exit', base=True, available_for=['TEST|Console'])


@exit.command()
async def _(msg: Bot.MessageSession):
    confirm = await msg.wait_confirm(msg.locale.t("core.message.confirm"), append_instruction=False, delete=False)
    if confirm:
        print('Exited.')
        sys.exit()