from core.builtins import Bot
from core.component import module
from core.logger import Logger
from database import BotDBUtil
from modules.wiki.utils.bot import BotAccount, LoginFailed
from modules.wiki.utils.dbutils import BotAccount as BotAccountDB
from modules.wiki.utils.wikilib import WikiLib

wb = module('wiki_bot', required_superuser=True,
            alias='wbot')


@wb.handle('login <apilink> <account> <password>')
async def _(msg: Bot.MessageSession, apilink: str, account: str, password: str):
    check = await WikiLib(apilink).check_wiki_available()
    if check.available:
        try:
            login = await BotAccount._login(check.value.api, account, password)
            BotAccountDB.add(check.value.api, account, password)
            BotAccount.cookies[check.value.api] = login
            await msg.finish(msg.locale.t("wiki.message.wiki_bot.login.success"))
        except LoginFailed as e:
            Logger.error(f'Login failed: {e}')
            await msg.finish(msg.locale.t("wiki.message.wiki_bot.login.failed", detail=e))
    else:
        result = msg.locale.t('wiki.message.error.query') + \
            ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@wb.handle('logout <apilink>')
async def _(msg: Bot.MessageSession, apilink: str):
    BotAccountDB.remove(apilink)
    await msg.finish(msg.locale.t("success"))


@wb.handle('toggle')
async def _(msg: Bot.MessageSession):
    target_data = BotDBUtil.TargetInfo(msg)
    use_bot_account = target_data.options.get('use_bot_account')
    if use_bot_account:
        target_data.edit_option('use_bot_account', False)
        await msg.finish(msg.locale.t("wiki.message.wiki_bot.toggle.disable"))
    else:
        target_data.edit_option('use_bot_account', True)
        await msg.finish(msg.locale.t("wiki.message.wiki_bot.toggle.enable"))


@wb.hook('login_wiki_bots')
async def _(fetch: Bot.FetchTarget, ctx: Bot.ModuleHookContext):
    Logger.debug('Received login_wiki_bots hook: ' + str(ctx.args['cookies']))
    BotAccount.cookies.update(ctx.args['cookies'])
