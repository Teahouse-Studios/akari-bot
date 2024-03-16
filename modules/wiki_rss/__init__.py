from core.builtins import Bot
from core.component import module

ca = module('check_ab', required_superuser=True, hide=True, developers=['OasisAkari'])


@ca.hook()
async def check_ab(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('check_ab', **ctx.args)


cr = module('check_rc', required_superuser=True, hide=True, developers=['OasisAkari'])


@cr.hook()
async def check_rc(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('check_rc', **ctx.args)


cn = module('check_newbie', required_superuser=True, hide=True, developers=['OasisAkari'])


@cn.hook()
async def check_newbie(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('check_newbie', **ctx.args)