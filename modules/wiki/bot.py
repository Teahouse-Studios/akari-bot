from datetime import datetime, timedelta

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from core.logger import Logger
from core.queue.client import JobQueueClient
from core.scheduler import DateTrigger, IntervalTrigger
from .database.models import WikiBotAccountList
from .utils.bot import BotAccount, LoginFailed
from .utils.wikilib import WikiLib

wb = module("wiki_bot", required_superuser=True, doc=True, alias="wbot")


@wb.command("login <apilink> <account> <password>")
async def _(msg: Bot.MessageSession, apilink: str, account: str, password: str):
    check = await WikiLib(apilink).check_wiki_available()
    if check.available:
        try:
            login = await BotAccount._login(check.value.api, account, password)
            if await WikiBotAccountList.add(check.value.api, account, password):
                BotAccount.cookies[check.value.api] = login
                await msg.finish(I18NContext("wiki.message.wiki_bot.login.success"))
            else:
                await msg.finish(I18NContext("wiki.message.wiki_bot.login.already"))
        except LoginFailed as e:
            Logger.error(f"Login failed: {e}")
            await msg.finish(I18NContext("wiki.message.wiki_bot.login.failed", detail=e))
    else:
        result = [I18NContext("wiki.message.error.query")]
        if check.message:
            result.append(Plain(str(I18NContext("wiki.message.error.info")) + check.message))
        await msg.finish(result)


@wb.command("logout <apilink>")
async def _(msg: Bot.MessageSession, apilink: str):
    check = await WikiLib(apilink).check_wiki_info_from_database_cache()
    if check.available:
        apilink = check.value.api
    if await WikiBotAccountList.remove(apilink):
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))


@wb.command("toggle")
async def _(msg: Bot.MessageSession):
    use_bot_account = msg.session_info.target_info.target_data.get("use_bot_account")
    if use_bot_account:
        await msg.session_info.target_info.edit_target_data("use_bot_account", False)
        await msg.finish(I18NContext("wiki.message.wiki_bot.toggle.disable"))
    else:
        await msg.session_info.target_info.edit_target_data("use_bot_account", True)
        await msg.finish(I18NContext("wiki.message.wiki_bot.toggle.enable"))


@wb.hook("login_wiki_bots")
async def _(ctx: Bot.ModuleHookContext):
    Logger.debug("Received login_wiki_bots hook: " + str(ctx.args["cookies"]))


@wb.schedule(DateTrigger(datetime.now() + timedelta(seconds=30)))
@wb.schedule(IntervalTrigger(minutes=30))
async def _():
    Logger.info("Start login wiki bot account...")
    await BotAccount.login()
    await JobQueueClient.trigger_hook("wikilog.keepalive")
    Logger.success("Successfully login wiki bot account.")
