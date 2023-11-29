from core.builtins import Bot
from core.component import module

mcv_rss = module('mcv_rss',
                 developers=['OasisAkari', 'Dianliang233'],
                 recommend_modules=['mcv_jira_rss', 'mcbv_jira_rss', 'mcdv_jira_rss', 'mclgv_jira_rss'],
                 desc='{mcv_rss.help.mcv_rss.desc}', alias='mcvrss')


@mcv_rss.hook()
async def mcv_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mcv_rss', **ctx.args)


mcbv_rss = module('mcbv_rss', developers=['OasisAkari'],
                  recommend_modules=['mcbv_jira_rss'],
                  desc='{mcv_rss.help.mcbv_rss.desc}', alias='mcbvrss')


@mcbv_rss.hook()
async def mcbv_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mcbv_rss', **ctx.args)


mcv_jira_rss = module('mcv_jira_rss', developers=['OasisAkari', 'Dianliang233'],
                      recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcdv_jira_rss', 'mclgv_jira_rss'],
                      desc='{mcv_rss.help.mcv_jira_rss.desc}', alias='mcvjirarss')


@mcv_jira_rss.hook()
async def mcv_jira_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mcv_jira_rss', **ctx.args)


mcbv_jira_rss = module('mcbv_jira_rss',
                       developers=['OasisAkari', 'Dianliang233'],
                       recommend_modules=['mcv_rss', 'mcv_jira_rss', 'mcdv_jira_rss', 'mclgv_jira_rss'],
                       desc='{mcv_rss.help.mcbv_jira_rss.desc}', alias='mcbvjirarss')


@mcbv_jira_rss.hook()
async def mcbv_jira_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mcbv_rss', **ctx.args)


mcdv_jira_rss = module('mcdv_jira_rss',
                       developers=['OasisAkari', 'Dianliang233'],
                       recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcv_jira_rss', 'mclgv_jira_rss'],
                       desc='{mcv_rss.help.mcdv_jira_rss.desc}', alias='mcdvjirarss')


@mcdv_jira_rss.hook()
async def mcdv_jira_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mcdv_rss', **ctx.args)


mclgv_jira_rss = module('mclgv_jira_rss',
                       developers=['OasisAkari', 'Dianliang233'],
                       recommend_modules=['mcv_rss', 'mcbv_jira_rss', 'mcv_jira_rss', 'mcdv_jira_rss'],
                       desc='{mcv_rss.help.mclgv_jira_rss.desc}', alias='mclgvjirarss')


@mclgv_jira_rss.hook()
async def mclgv_jira_rss(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message('mclgv_rss', **ctx.args)
