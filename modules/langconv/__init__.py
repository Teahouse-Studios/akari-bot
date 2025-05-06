from langconv.converter import LanguageConverter
from langconv.language.zh import zh_cn, zh_hk, zh_tw

from core.builtins import Bot, I18NContext
from core.component import module
from core.dirty_check import check_bool, rickroll

lc_ = module("langconv", developers=["Dianliang233"], alias=["lc"], doc=True)

lc_zh_cn = LanguageConverter.from_language(zh_cn)
lc_zh_hk = LanguageConverter.from_language(zh_hk)
lc_zh_tw = LanguageConverter.from_language(zh_tw)


@lc_.command("<language> <content> {[I18N:langconv.help]}")
async def _(msg: Bot.MessageSession, language: str, content: str):
    if not language.startswith("zh"):
        language = "zh-" + language
    language = language.replace("_", "-").lower()
    if language not in ("zh-cn", "zh-hk", "zh-tw"):
        await msg.finish(I18NContext("langconv.message.unsupported_language"))
    lc = {"zh-cn": lc_zh_cn, "zh-hk": lc_zh_hk, "zh-tw": lc_zh_tw}[language]
    res = lc.convert(content)
    if await check_bool(res):
        await msg.finish(rickroll())
    await msg.finish(res)
