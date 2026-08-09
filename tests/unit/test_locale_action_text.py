"""locale 命令的语言入口与协助翻译链接测试。"""

from types import SimpleNamespace

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, I18NContextElement, PlainElement, URLElement
from core.i18n import Locale, get_available_locales
from core.tester import func_case, Tester
from modules.core.utils import build_locale_list, build_locale_overview


def _msg(support_action_text: bool = True):
    return SimpleNamespace(
        session_info=SimpleNamespace(
            locale=Locale("zh_cn"),
            prefixes=["~"],
            support_action_text=support_action_text,
        )
    )


def _test_locale_list_action_texts():
    msg = _msg()
    parts = build_locale_list(msg)
    if len(parts) != 1 or not isinstance(parts[0], I18NContextElement):
        return False
    langlist = parts[0].kwargs.get("langlist")
    if not isinstance(langlist, MessageChain):
        return False
    actions = [element for element in langlist.values if isinstance(element, ActionTextElement)]
    locales = get_available_locales()
    if len(actions) != len(locales) or len(langlist.values) != len(locales) * 2:
        return False
    for index, (action, lang) in enumerate(zip(actions, locales, strict=True)):
        if action.text.text != f"~locale {lang}" or action.show.text != Locale(lang).t("language"):
            return False
        separator = langlist.values[1 + index * 2]
        expected_separator = "\n" if index + 1 < len(locales) else " "
        if not isinstance(separator, PlainElement) or separator.text != expected_separator:
            return False
    return True


def _test_locale_list_plain_fallback():
    msg = _msg(support_action_text=False)
    parts = build_locale_list(msg)
    expected = "\n".join(["支持的语言列表：", *(Locale(lang).t("language") for lang in get_available_locales())])
    return (
        len(parts) == 1
        and isinstance(parts[0], I18NContextElement)
        and msg.session_info.locale.t(parts[0].key, **parts[0].kwargs) == expected
    )


def _test_locale_contribute_uses_url_element():
    parts = build_locale_overview(_msg(), "https://example.com/translate")
    contribute = parts[-1]
    if not isinstance(contribute, I18NContextElement):
        return False
    url = contribute.kwargs.get("url")
    return (
        isinstance(url, MessageChain)
        and len(url.values) == 1
        and isinstance(url.values[0], URLElement)
        and url.values[0].url == "https://example.com/translate"
        and url.values[0].trusted is True
    )


@func_case
async def test_locale_action_text(tester: Tester):
    await tester.test(_test_locale_list_action_texts, "语言列表 ActionText 测试")
    await tester.test(_test_locale_list_plain_fallback, "语言列表纯文本降级测试")
    await tester.test(_test_locale_contribute_uses_url_element, "协助翻译链接 Url 元素测试")
    return tester
