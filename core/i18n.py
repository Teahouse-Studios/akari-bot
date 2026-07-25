from akari_bot_i18n.i18n import Locale, load_locale_file, get_available_locales

from core.constants import lang_list, all_locales_path

# TODO: 由于Config自动补充需要加载 I18N，但是加载模块过程中其他模块会被先导入，导致自动补充的 I18N 失效... 暂时将 locale 放在顶层加载...
# 待后续解决...

locale_loaded_err = load_locale_file(list(lang_list.keys()), all_locales_path)

__all__ = ["Locale", "load_locale_file", "get_available_locales", "locale_loaded_err"]
