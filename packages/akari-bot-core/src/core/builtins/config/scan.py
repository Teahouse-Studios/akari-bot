"""配置模板扫描。"""

import importlib

from loguru import logger

from core.builtins.config import CFGManager
from core.builtins.config.bootstrap import bootstrap_config


def iter_config_template_modules() -> list[str]:
    """列出全部配置模板的模块名。

    :return: 配置模板的模块名列表，核心配置排在最前。
    """
    from core.plugin import iter_bot_packages, iter_module_packages

    names = ["core.config.base"]
    # 只检查插件目录里是否存在 config.py，不导入插件本身，避免在配置引导前触发注册。
    for package in (*iter_bot_packages(), *iter_module_packages()):
        if (package.path / "config.py").is_file():
            names.append(f"{package.package}.config")
    return names


def scan_config_templates() -> list[str]:
    """导入全部配置模板，补全配置文件中缺失的键。

    :return: 加载失败的配置模板模块名列表，空列表表示全部成功。
    """
    bootstrap_config()
    failed = []
    for module_name in iter_config_template_modules():
        try:
            importlib.import_module(module_name)
        except Exception:
            failed.append(module_name)
            logger.exception(f"[Config] Failed to load config template {module_name}: ")
    repaired_comments = CFGManager.repair_i18n_comments()
    if repaired_comments:
        logger.info(f"[Config] Repaired {repaired_comments} unresolved i18n comments.")
    CFGManager.save()
    return failed
