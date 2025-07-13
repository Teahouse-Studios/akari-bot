from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain, I18NMessageChain, PlatformMessageChain
from core.builtins.message.internal import Plain
from core.builtins.utils import command_prefix
from core.component import module
from core.i18n import Locale
from core.logger import Logger
from core.scheduler import CronTrigger
from core.utils.image import msgchain2image
from modules.weekly import get_weekly, get_teahouse_rss

weekly_rss = module(
    "weekly_rss",
    desc="{I18N:weekly_rss.help.desc}",
    developers=["Dianliang233"],
    alias="weeklyrss",
    doc=True,
    rss=True,
)


teahouse_weekly_rss = module(
    "teahouse_weekly_rss",
    desc="{I18N:weekly_rss.help.teahouse_weekly_rss.desc}",
    developers=["OasisAkari"],
    alias=["teahouseweeklyrss", "teahouserss"],
    doc=True,
    rss=True,
)


@weekly_rss.schedule(CronTrigger.from_crontab("0 9 * * MON"))
async def _():
    Logger.info("Checking MCWZH weekly...")

    weekly_cn = MessageChain.assign(await get_weekly())
    weekly_tw = MessageChain.assign(await get_weekly(zh_tw=True))
    w_cn_qq = MessageChain.assign(await get_weekly(True))
    w_tw_qq = MessageChain.assign(await get_weekly(True, zh_tw=True))
    w_cn_qq = [
        Plain(Locale("zh_cn").t("weekly_rss.message", prefix=command_prefix[0]))
    ] + w_cn_qq.as_sendable()
    w_tw_qq = [
        Plain(Locale("zh_tw").t("weekly_rss.message", prefix=command_prefix[0]))
    ] + w_tw_qq.as_sendable()
    weekly_cn_qq = MessageChain.assign(await msgchain2image(w_cn_qq))
    weekly_tw_qq = MessageChain.assign(await msgchain2image(w_tw_qq))
    post_msg = I18NMessageChain.assign({"zh_cn": weekly_cn, "zh_tw": weekly_tw, "default": weekly_cn})
    post_msg_qq = I18NMessageChain.assign({
        "zh_cn": weekly_cn_qq,
        "zh_tw": weekly_tw_qq,
        "default": weekly_cn_qq,
    })
    await Bot.post_message("weekly_rss", PlatformMessageChain.assign({'QQ': post_msg_qq, 'default': post_msg}))
    Logger.success("Weekly checked.")


@teahouse_weekly_rss.schedule(trigger=CronTrigger.from_crontab("30 9 * * MON"))
async def _():
    Logger.info("Checking teahouse weekly...")

    weekly = await get_teahouse_rss()
    Logger.info("Checking teahouse weekly...")

    weekly_cn = MessageChain.assign(Plain(
        Locale("zh_cn").t(
            "weekly_rss.message.teahouse_weekly_rss", prefix=command_prefix[0]
        )
        + weekly
    ))
    weekly_tw = MessageChain.assign(
        Plain(
            Locale("zh_tw").t(
                "weekly_rss.message.teahouse_weekly_rss", prefix=command_prefix[0]
            )
            + weekly
        ))
    weekly_cn_qq = MessageChain.assign(await msgchain2image(weekly_cn))
    weekly_tw_qq = MessageChain.assign(await msgchain2image(weekly_tw))
    post_msg = I18NMessageChain.assign({"zh_cn": weekly_cn, "zh_tw": weekly_tw, "default": weekly_cn})
    post_msg_qq = I18NMessageChain.assign({'zh_cn': weekly_cn_qq, 'zh_tw': weekly_tw_qq, 'default': weekly_cn_qq})
    await Bot.post_message("teahouse_weekly_rss", PlatformMessageChain.assign({'QQ': post_msg_qq, 'default': post_msg}))
    Logger.success("Teahouse Weekly checked.")
