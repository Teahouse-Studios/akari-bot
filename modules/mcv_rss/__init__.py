from core.builtins import Bot
from core.component import module

mcv_rss = module(
    "mcv_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcv_jira_rss"],
    desc="[I18N:mcv_rss.help.mcv_rss.desc]",
    alias="mcvrss",
    doc=True,
    rss=True,
)


@mcv_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcv_rss", **ctx.args)


mcbv_rss = module(
    "mcbv_rss",
    developers=["OasisAkari"],
    recommend_modules=["mcbv_jira_rss"],
    desc="[I18N:mcv_rss.help.mcbv_rss.desc]",
    alias="mcbvrss",
    doc=True,
    rss=True,
)


@mcbv_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcbv_rss", **ctx.args)


mcv_jira_rss = module(
    "mcv_jira_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcv_rss"],
    desc="[I18N:mcv_rss.help.mcv_jira_rss.desc]",
    alias="mcvjirarss",
    doc=True,
    rss=True,
)


@mcv_jira_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcv_jira_rss", **ctx.args)


mcbv_jira_rss = module(
    "mcbv_jira_rss",
    developers=["OasisAkari", "Dianliang233"],
    recommend_modules=["mcbv_rss"],
    desc="[I18N:mcv_rss.help.mcbv_jira_rss.desc]",
    alias="mcbvjirarss",
    doc=True,
    rss=True,
)


@mcbv_jira_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcbv_rss", **ctx.args)


mcdv_rss = module(
    "mcdv_rss",
    developers=["OasisAkari", "Dianliang233"],
    desc="[I18N:mcv_rss.help.mcdv_rss.desc]",
    alias=["mcdvrss", "mcdv_rss", "mcdvjirarss"],
    doc=True,
    hidden=True,
    rss=True,
)


@mcdv_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mcdv_rss", **ctx.args)


mclgv_rss = module(
    "mclgv_rss",
    developers=["OasisAkari", "Dianliang233"],
    desc="[I18N:mcv_rss.help.mclgv_rss.desc]",
    alias=["mclgvrss", "mclgv_rss", "mclgvjirarss"],
    doc=True,
    hidden=True,
    rss=True,
)


@mclgv_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    await fetch.post_message("mclgv_rss", **ctx.args)
