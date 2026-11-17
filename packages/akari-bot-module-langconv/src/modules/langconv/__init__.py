from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.component import module

lc_ = module("langconv", developers=["Dianliang233"], alias=["lc"], doc=True)

_converters = None


def get_converters():
    global _converters
    if _converters is None:
        from langconv.converter import LanguageConverter
        from langconv.language.zh import zh_cn, zh_hk, zh_tw

        _converters = {
            "zh-cn": LanguageConverter.from_language(zh_cn),
            "zh-hk": LanguageConverter.from_language(zh_hk),
            "zh-tw": LanguageConverter.from_language(zh_tw),
        }
    return _converters


@lc_.command("<language> <content> {{I18N:langconv.help}}")
async def _(msg: Bot.MessageSession, language: str, content: str):
    if not language.startswith("zh"):
        language = "zh-" + language
    language = language.replace("_", "-").lower()
    if language not in ("zh-cn", "zh-hk", "zh-tw"):
        await msg.finish(I18NContext("langconv.message.unsupported_language"))
    lc = get_converters()[language]
    res = lc.convert(content)
    await msg.finish(res)
