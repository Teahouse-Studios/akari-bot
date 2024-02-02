from core.builtins import Bot
from core.component import module
from core.logger import Logger
from database import BotDBUtil
from modules.wiki.utils.bot import BotAccount, LoginFailed
from modules.wiki.utils.dbutils import BotAccount as BotAccountDB
from modules.wiki.utils.wikilib import WikiLib

wb = module('wiki_bot', required_superuser=True,
             alias='wbot')


@wb.handle('login <apiLink> <account> <password>')
async def _(msg: Bot.MessageSession):
    api_link = msg.parsed_msg['<apiLink>']
    account = msg.parsed_msg['<account>']
    password = msg.parsed_msg['<password>']
    check = await WikiLib(api_link).check_wiki_available()
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


@wb.handle('logout <apiLink>')
async def _(msg: Bot.MessageSession):
    api_link = msg.parsed_msg['<apiLink>']
    BotAccountDB.remove(api_link)
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