"""core.i18n 国际化系统单元测试。"""

from core.i18n import Locale, load_locale_file, get_available_locales
from core.tester import func_case, Tester


def _test_locale_create():
    """Locale: 创建 Locale 实例"""
    try:
        locale = Locale("zh_cn")
        return locale is not None
    except Exception:
        return False


def _test_locale_t_existing_key():
    """Locale: 获取已存在的 i18n 键"""
    try:
        locale = Locale("zh_cn")
        result = locale.t("core.help.desc", locale_failed_prompt=False)
        return isinstance(result, str) and len(result) > 0 and result != "core.help.desc"
    except Exception:
        return False


def _test_locale_t_missing_key():
    """Locale: 获取不存在的键应返回包含键名的字符串"""
    try:
        locale = Locale("zh_cn")
        key = "nonexistent.key.xyz.12345"
        result = locale.t(key, fallback=False, locale_failed_prompt=False)
        return isinstance(result, str) and key in result
    except Exception:
        return False


def _test_locale_t_kwargs_substitution():
    """Locale: 参数替换应生效"""
    try:
        locale = Locale("zh_cn")
        key = "tos.message.reason"
        result = locale.t(key, reason="test_reason", locale_failed_prompt=False)
        return "test_reason" in result
    except Exception:
        return False


def _test_locale_t_str_i18n_key():
    """Locale: t_str 应处理 {I18N:key} 模板"""
    try:
        locale = Locale("zh_cn")
        result = locale.t_str("{I18N:core.help.desc}")
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


def _test_locale_t_str_no_template():
    """Locale: t_str 无模板时返回原文"""
    try:
        locale = Locale("zh_cn")
        result = locale.t_str("plain text")
        return result == "plain text"
    except Exception:
        return False


def _test_load_locale_file():
    """load_locale_file: 加载语言文件不报错"""
    try:
        from core.constants import lang_list, all_locales_path

        errors = load_locale_file(list(lang_list.keys()), all_locales_path)
        return isinstance(errors, list)
    except Exception:
        return False


def _test_get_available_locales():
    """get_available_locales: 获取可用语言列表"""
    try:
        locales = get_available_locales()
        return isinstance(locales, list) and len(locales) > 0
    except Exception:
        return False


@func_case
async def test_i18n(tester: Tester):
    """core.i18n: 国际化系统测试"""
    await tester.test(_test_locale_create, "Locale 创建测试")
    await tester.test(_test_locale_t_existing_key, "Locale.t 已存在键测试")
    await tester.test(_test_locale_t_missing_key, "Locale.t 不存在键测试")
    await tester.test(_test_locale_t_kwargs_substitution, "Locale.t 参数替换测试")
    await tester.test(_test_locale_t_str_i18n_key, "Locale.t_str I18N 键测试")
    await tester.test(_test_locale_t_str_no_template, "Locale.t_str 无模板测试")
    await tester.test(_test_load_locale_file, "load_locale_file 加载测试")
    await tester.test(_test_get_available_locales, "get_available_locales 测试")
    return tester
