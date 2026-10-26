"""core.i18n 国际化系统单元测试。"""

from core.i18n import Locale
from core.tester import func_case, Tester


def _test_locale_t_existing_key():
    try:
        locale = Locale("zh_cn")
        result = locale.t("core.help.desc", locale_failed_prompt=False)
        return isinstance(result, str) and len(result) > 0 and result != "core.help.desc"
    except Exception:
        return False


def _test_locale_t_missing_key():
    try:
        locale = Locale("zh_cn")
        key = "nonexistent.key.xyz.12345"
        result = locale.t(key, fallback=False, locale_failed_prompt=False)
        return isinstance(result, str) and key in result
    except Exception:
        return False


def _test_locale_t_kwargs_substitution():
    try:
        locale = Locale("zh_cn")
        key = "tos.message.reason"
        result = locale.t(key, reason="test_reason", locale_failed_prompt=False)
        return "test_reason" in result
    except Exception:
        return False


def _test_locale_t_str_i18n_key():
    try:
        locale = Locale("zh_cn")
        result = locale.t_str("{I18N:core.help.desc}")
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


@func_case
async def test_i18n(tester: Tester):
    """core.i18n: 国际化系统测试"""
    await tester.test(_test_locale_t_existing_key, "Locale.t 已存在键测试")
    await tester.test(_test_locale_t_missing_key, "Locale.t 不存在键测试")
    await tester.test(_test_locale_t_kwargs_substitution, "Locale.t 参数替换测试")
    await tester.test(_test_locale_t_str_i18n_key, "Locale.t_str I18N 键测试")
    return tester
