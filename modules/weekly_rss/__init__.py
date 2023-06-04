from core.builtins import Bot, Image, Plain, command_prefix
from core.component import module
from core.logger import Logger
from core.scheduler import CronTrigger
from core.utils.i18n import Locale
from core.utils.image import msgchain2image
from modules.weekly import get_weekly
from modules.weekly.teahouse import get_rss as get_teahouse_rss

weekly_rss = module('weekly_rss',
                    desc='{weekly_rss.help.desc}',
                    developers=['Dianliang233'], alias='weeklyrss')


@weekly_rss.handle(CronTrigger.from_crontab('0 9 * * MON'))
async def weekly_rss():
    Logger.info('Checking MCWZH weekly...')

    weekly_cn = await get_weekly(True if Bot.FetchTarget.name == 'QQ' else False)
    weekly_tw = await get_weekly(True if Bot.FetchTarget.name == 'QQ' else False, zh_tw=True)
    if Bot.FetchTarget.name == 'QQ':
        weekly_cn = [Plain(Locale('zh_cn').t('weekly_rss.message', prefix=command_prefix[0]))] + weekly_cn
        weekly_tw = [Plain(Locale('zh_tw').t('weekly_rss.message', prefix=command_prefix[0]))] + weekly_tw
        weekly_cn = Image(await msgchain2image(weekly_cn))
        weekly_tw = Image(await msgchain2image(weekly_tw))
    post_msg = {'zh_cn': weekly_cn, 'zh_tw': weekly_tw, 'fallback': weekly_cn}
    await Bot.FetchTarget.post_message('weekly_rss', post_msg, i18n=True)
    Logger.info('Weekly checked.')


teahouse_weekly_rss = module('teahouse_weekly_rss',

                             desc='{weekly_rss.help.teahouse_weekly_rss.desc}',
                             developers=['OasisAkari'], alias=['teahouseweeklyrss', 'teahouserss'])


@teahouse_weekly_rss.handle(trigger=CronTrigger.from_crontab('30 9 * * MON'))
async def weekly_rss():
    Logger.info('Checking teahouse weekly...')

    weekly = await get_teahouse_rss()
    if Bot.FetchTarget.name == 'QQ':
        weekly_cn = [
            Plain(
                Locale('zh_cn').t(
                    'weekly_rss.message.teahouse_weekly_rss',
                    prefix=command_prefix[0]) +
                weekly)]
        weekly_tw = [
            Plain(
                Locale('zh_tw').t(
                    'weekly_rss.message.teahouse_weekly_rss',
                    prefix=command_prefix[0]) +
                weekly)]
        weekly_cn = Image(await msgchain2image(weekly_cn))
        weekly_tw = Image(await msgchain2image(weekly_tw))
        post_msg = {'zh_cn': weekly_cn, 'zh_tw': weekly_tw, 'fallback': weekly_cn}
        await Bot.FetchTarget.post_message('teahouse_weekly_rss', post_msg, i18n=True)
    else:
        await Bot.FetchTarget.post_message('teahouse_weekly_rss', weekly)
    Logger.info('Teahouse Weekly checked.')
