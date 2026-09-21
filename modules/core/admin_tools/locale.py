import orjson
from akari_bot_i18n.i18n import build_locale_snapshot

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, I18NContext, Plain, Url
from core.config.base import CoreConfig
from core.constants import all_locales_path, lang_list, weblate_lang_codes
from core.i18n import Locale, get_available_locales
from core.utils.http import get_url
from core.constants.path import cache_path
from modules.core.common_tools.setup import setup

WEBLATE_LANGUAGES_API = "https://hosted.weblate.org/api/projects/akaribot/languages/"
TRANSLATION_PROGRESS_THRESHOLD = 95.0
WEBLATE_LANGUAGES_CACHE = cache_path / "weblate_languages.json"


def build_locale_list(msg: Bot.MessageSession) -> list:
    """构造逐行显示的可用语言列表。"""
    locales = [(lang, Locale(lang).t("language")) for lang in get_available_locales()]
    if not msg.session_info.support_action_text:
        return [I18NContext("core.message.setup.locale.langlist", langlist="\n".join(name for _, name in locales))]

    prefix = msg.session_info.prefixes[0]
    parts = []
    for index, (lang, name) in enumerate(locales):
        parts.append(ActionText(f"{prefix}setup locale {lang}", show=name))
        parts.append(Plain("\n" if index + 1 < len(locales) else " ", disable_joke=True))
    return [I18NContext("core.message.setup.locale.langlist", langlist=MessageChain.assign(parts))]


def build_locale_overview(msg: Bot.MessageSession, locale_url: str | None) -> list:
    """构造语言命令的概览消息。"""
    res = [
        I18NContext("core.message.setup.locale.prompt", lang="{I18N:language}"),
        I18NContext(
            "core.message.setup.locale.set.prompt",
            cmd=ActionText(f"{msg.session_info.prefixes[0]}setup locale "),
        ),
        *build_locale_list(msg),
    ]
    if locale_url:
        res.append(
            I18NContext(
                "core.message.setup.locale.contribute",
                url=MessageChain.assign(Url(locale_url, trusted=True)),
            )
        )
    return res


async def get_weblate_languages() -> list | None:
    if WEBLATE_LANGUAGES_CACHE.is_file():
        try:
            languages = orjson.loads(WEBLATE_LANGUAGES_CACHE.read_bytes())
        except Exception:
            languages = None
        if isinstance(languages, list):
            return languages
        # 缓存损坏时移除，避免后续反复命中坏文件。
        try:
            WEBLATE_LANGUAGES_CACHE.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        languages = await get_url(WEBLATE_LANGUAGES_API, fmt="json", timeout=5, logging_err_resp=False)
    except Exception:
        return None
    if not isinstance(languages, list):
        return None
    try:
        WEBLATE_LANGUAGES_CACHE.parent.mkdir(parents=True, exist_ok=True)
        WEBLATE_LANGUAGES_CACHE.write_bytes(orjson.dumps(languages))
    except OSError:
        pass
    return languages


async def build_translation_notice(lang: str):
    weblate_code = weblate_lang_codes.get(lang)
    if not weblate_code:
        return None
    languages = await get_weblate_languages()
    if not languages:
        return None
    entry = next((item for item in languages if isinstance(item, dict) and item.get("code") == weblate_code), None)
    if not entry:
        return None
    progress = entry.get("translated_percent")
    if not isinstance(progress, (int, float)) or progress >= TRANSLATION_PROGRESS_THRESHOLD:
        return None
    return [
        I18NContext(
            "core.message.setup.locale.translation_progress", name=Locale(lang).t("language"), percent=f"{progress:g}"
        ),
        Url(entry.get("url") or CoreConfig.locale_url, trusted=True),
    ]


@setup.command("locale {{I18N:core.help.setup.locale.desc}}")
async def _(msg: Bot.MessageSession):
    await msg.send_message(build_locale_overview(msg, CoreConfig.locale_url))
    await msg.finish(await build_translation_notice(msg.session_info.locale.locale))


@setup.command("locale [<lang>] {{I18N:core.help.setup.locale.set}}", required_admin=True)
async def _(msg: Bot.MessageSession, lang: str):
    if lang in get_available_locales():
        await msg.session_info.target_union_info.edit_attr("locale", lang)
        await msg.send_message(Locale(lang).t("message.success"))
        await msg.finish(await build_translation_notice(lang))
    else:
        await msg.finish([I18NContext("core.message.setup.locale.set.invalid"), *build_locale_list(msg)])


@setup.command("locale reload {{I18N:core.help.setup.locale.reload}}", required_superuser=True)
async def _(msg: Bot.MessageSession):
    err = build_locale_snapshot(list(lang_list.keys()), all_locales_path, "akari-bot")
    if len(err) == 0:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(
            [I18NContext("core.message.setup.locale.reload.failed"), Plain("\n".join(err), disable_joke=True)]
        )
