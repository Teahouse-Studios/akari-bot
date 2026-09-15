from akari_bot_webrender.functions.options import StatusOptions

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module
from core.utils.web_render import check_web_render_status, close_web_render, init_web_render, web_render

wr = module("webrender", required_superuser=True, base=True, doc=True)


@wr.command("status {{I18N:core.help.webrender.status}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(str(await web_render.status(StatusOptions())))


@wr.command("start {{I18N:core.help.webrender.start}}")
async def _(msg: Bot.MessageSession):
    if await init_web_render():
        Bot.Info.web_render_status = await check_web_render_status()
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))


@wr.command("stop {{I18N:core.help.webrender.stop}}")
async def _(msg: Bot.MessageSession):
    await close_web_render()
    Bot.Info.web_render_status = await check_web_render_status()
    await msg.finish(I18NContext("message.success"))


@wr.command("reload {{I18N:core.help.webrender.reload}}")
async def _(msg: Bot.MessageSession):
    await close_web_render()
    if await init_web_render():
        Bot.Info.web_render_status = await check_web_render_status()
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))
