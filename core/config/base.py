from core.builtins.config.decorator import on_base_config
from core.constants.default import default_locale as default_locale_default
from core.constants.version import config_version as config_version_default


@on_base_config()
class BaseConfig:
    default_locale: str = default_locale_default
    config_version: int = config_version_default
