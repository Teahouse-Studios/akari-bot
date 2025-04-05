from core.builtins import Bot
from core.component import module
from core.logger import Logger
from modules.wiki.database.models import WikiBotAccountList
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
                await msg.finish(msg.locale.t("wiki.message.wiki_bot.login.success"))
            else:
                await msg.finish(msg.locale.t("wiki.message.wiki_bot.login.already"))
        except LoginFailed as e:
            Logger.error(f"Login failed: {e}")
            await msg.finish(
                msg.locale.t("wiki.message.wiki_bot.login.failed", detail=e)
            )
    else:
        result = msg.locale.t("wiki.message.error.query") + (
            "\n" + msg.locale.t("wiki.message.error.info") + check.message
            if check.message != ""
            else ""
        )
        await msg.finish(result)


@wb.command("logout <apilink>")
async def _(msg: Bot.MessageSession, apilink: str):
    check = await WikiLib(apilink).check_wiki_info_from_database_cache()
    if check.available:
        apilink = check.value.api
    if await WikiBotAccountList.remove(apilink):
        await msg.finish(msg.locale.t("message.success"))
    else:
        await msg.finish(msg.locale.t("message.failed"))


@wb.command("toggle")
async def _(msg: Bot.MessageSession):
    use_bot_account = msg.target_info.target_data.get("use_bot_account")
    if use_bot_account:
        await msg.target_info.edit_target_data("use_bot_account", False)
        await msg.finish(msg.locale.t("wiki.message.wiki_bot.toggle.disable"))
    else:
        await msg.target_info.edit_target_data("use_bot_account", True)
        await msg.finish(msg.locale.t("wiki.message.wiki_bot.toggle.enable"))


@wb.hook("login_wiki_bots")
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    Logger.debug("Received login_wiki_bots hook: " + str(ctx.args["cookies"]))
    BotAccount.cookies.update(ctx.args["cookies"])
