from core.builtins import Bot
from core.component import module

mcr = module('mc_crowdin', developers=['OasisAkari'],
             desc='', alias='mccrowdin', exclude_from=['QQ', 'QQ|Group', 'QQ|Guild'])


@mcr.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mc_crowdin', **ctx.args)


mcrs = module('mc_crowdin', developers=['OasisAkari'],
              desc='', alias='mccrowdin', available_for=['QQ', 'QQ|Group', 'QQ|Guild'], required_superuser=True)


@mcrs.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mc_crowdin', **ctx.args)
