"""表外基础配置及历史导入路径兼容层。"""

from core.config.decorator import on_base_config
from core.constants.default import default_locale as default_locale_default
from core.constants.version import config_version as config_version_default


# 位于 config.toml 中任何表之外的顶层键值对。它们在配置文件建立时由 config_generate.py 写入，
# 并由 core/config/update.py 的版本迁移维护，声明在此仅为提供一个带类型的读取入口。
@on_base_config()
class BaseConfig:
    default_locale: str = default_locale_default
    config_version: int = config_version_default


# 保留既有导入路径，避免第三方模块因配置模板的物理拆分立即失效。项目内部的新代码应从所属领域模块导入。
from core.config.core import CoreConfig, CoreSecretConfig
from core.config.jobqueue import JobQueueConfig, JobQueueSecretConfig
from core.config.s3 import S3Config, S3SecretConfig
from core.config.webrender import WebRenderConfig

__all__ = [
    "BaseConfig",
    "CoreConfig",
    "CoreSecretConfig",
    "JobQueueConfig",
    "JobQueueSecretConfig",
    "S3Config",
    "S3SecretConfig",
    "WebRenderConfig",
]
