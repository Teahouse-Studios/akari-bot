from core.builtins import Bot
from core.component import module
from langconv.converter import LanguageConverter
from langconv.language.zh import zh_cn, zh_hk, zh_tw

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
    await msg.finish(lc.convert(content))
