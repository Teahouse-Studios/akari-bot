import time
from langconv.converter import LanguageConverter
from langconv.language.zh import zh_cn, zh_hk, zh_tw

from core.builtins import Bot
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.exceptions import NoReportException

l = module('langconv', developers=['Dianliang233'], alias={'lc': 'langconv'}, desc='{langconv.help}')

lc_zh_cn = LanguageConverter.from_language(zh_cn)
lc_zh_hk = LanguageConverter.from_language(zh_hk)
lc_zh_tw = LanguageConverter.from_language(zh_tw)


@l.handle('<language> <content> {{langconv.help}}')
async def _(msg: Bot.MessageSession, language: str, content: str):
    language = language.replace('_', '-')
    if language not in ('zh-cn', 'zh-hk', 'zh-tw'):
        await msg.finish(msg.locale.t('langconv.message.unsupported_language'))
    lc = {'zh-cn': lc_zh_cn, 'zh-hk': lc_zh_hk, 'zh-tw': lc_zh_tw}[language]
    start = time.perf_counter_ns()
    res = lc.convert(content)
    stop = time.perf_counter_ns()
    delta = (stop - start) / 1000000
    if await check_bool(res):
        raise NoReportException(rickroll())
    await msg.finish(res + '\n' + msg.locale.t('langconv.message.running_time', time=delta))
