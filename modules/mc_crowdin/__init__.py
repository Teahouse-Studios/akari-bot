from core.builtins import Bot
from core.component import module

mcr = module(
    "mc_crowdin",
    developers=["OasisAkari"],
    alias="mccrowdin",
    exclude_from=["QQ|Private", "QQ|Group", "QQ|Guild"],
    rss=True,
    required_superuser=True,
)


@mcr.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mc_crowdin", **ctx.args)
