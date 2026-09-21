"""配置模板扫描。"""

import importlib
from pathlib import Path

from loguru import logger

from core.config import CFGManager


def iter_config_template_modules() -> list[str]:
    """列出全部配置模板的模块名。

    :return: 配置模板的模块名列表，核心配置排在最前。
    """
    import bots
    import modules

    names = ["core.config.base"]
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        # 按名称排序以固定生成顺序，避免同一批配置项在多次生成间换序而反复改写配置文件
        for submodule in sorted(package_path.iterdir(), key=lambda path: path.name):
            if not submodule.is_dir() or submodule.name.startswith((".", "_")):
                continue
            if not (submodule / "config.py").is_file():
                continue
            if not (submodule / "__init__.py").is_file():
                # 目录形式的命名空间包仍可导入，配置照常补全；但其它按包枚举的代码看不见它，
                # 故此处仅告警，提示补上空的 __init__.py 以恢复常规包
                logger.warning(
                    f"[Config] {package.__name__}/{submodule.name} provides config.py without __init__.py; "
                    "its configuration is generated, but an empty __init__.py is required for it to be "
                    "visible to package-based enumeration."
                )
            names.append(f"{package.__name__}.{submodule.name}.config")
    return names


def scan_config_templates() -> list[str]:
    """导入全部配置模板，补全配置文件中缺失的键。

    :return: 加载失败的配置模板模块名列表，空列表表示全部成功。
    """
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
