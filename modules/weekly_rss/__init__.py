from core.builtins import Bot, Image, Plain, command_prefix, I18NContext, MessageChain
from core.component import module
from core.i18n import Locale
from core.logger import Logger
from core.utils.image import msgchain2image

weekly_rss = module(
    "weekly_rss",
    desc="{weekly_rss.help.desc}",
    developers=["Dianliang233"],
    alias="weeklyrss",
    doc=True,
    rss=True,
)


@weekly_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    weekly_cn = MessageChain(ctx.args["weekly_cn"])
    weekly_tw = MessageChain(ctx.args["weekly_tw"])
    if Bot.FetchTarget.name == "QQ":
        weekly_cn = [
            Plain(Locale("zh_cn").t("weekly_rss.message", prefix=command_prefix[0]))
        ] + weekly_cn.as_sendable()
        weekly_tw = [
            Plain(Locale("zh_tw").t("weekly_rss.message", prefix=command_prefix[0]))
        ] + weekly_tw.as_sendable()
        weekly_cn = [Image(x) for x in await msgchain2image(weekly_cn)]
        weekly_tw = [Image(x) for x in await msgchain2image(weekly_tw)]
    post_msg = {"zh_cn": weekly_cn, "zh_tw": weekly_tw, "fallback": weekly_cn}
    await fetch.post_message("weekly_rss", I18NContext(post_msg), i18n=True)
    Logger.success("Weekly checked.")


teahouse_weekly_rss = module(
    "teahouse_weekly_rss",
    desc="{weekly_rss.help.teahouse_weekly_rss.desc}",
    developers=["OasisAkari"],
    alias=["teahouseweeklyrss", "teahouserss"],
    doc=True,
    rss=True,
)


@teahouse_weekly_rss.hook()
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    Logger.info("Checking teahouse weekly...")

    weekly = ctx.args["weekly"]
    weekly_cn = [
        Plain(
            Locale("zh_cn").t(
                "weekly_rss.message.teahouse_weekly_rss", prefix=command_prefix[0]
            )
            + weekly
        )
    ]
    weekly_tw = [
        Plain(
            Locale("zh_tw").t(
                "weekly_rss.message.teahouse_weekly_rss", prefix=command_prefix[0]
            )
            + weekly
        )
    ]
    if Bot.FetchTarget.name == "QQ":
        weekly_cn = [Image(x) for x in await msgchain2image(weekly_cn)]
        weekly_tw = [Image(x) for x in await msgchain2image(weekly_tw)]
    post_msg = {"zh_cn": weekly_cn, "zh_tw": weekly_tw, "fallback": weekly_cn}
    await fetch.post_message("teahouse_weekly_rss", I18NContext(post_msg), i18n=True)
    Logger.success("Teahouse Weekly checked.")
