"""配置模板扫描。

配置的生成统一在 bot.py 的 pre_init() 中完成，bot 与 server 子进程一律只读，
因此这里必须把全部模板扫全：任何遗漏的键都会在子进程读取时抛出 ConfigOperationError。
"""

import importlib
import pkgutil
from pathlib import Path

from loguru import logger

from core.config import CFGManager


def iter_config_template_modules() -> list[str]:
    """列出全部配置模板的模块名。

    以文件是否存在判断模板有无，而非在导入时捕获 ModuleNotFoundError：后者无法区分
    「该 bot 或模块未提供 config.py」与「模板自身导入了不存在的依赖」两种情形，
    后一种会被静默跳过，形成本设计所要杜绝的漏键。

    亦不采用 importlib.util.find_spec()：该函数为取得 __path__ 会导入父包，
    将一并导入整个 bot 或模块包及其依赖，使配置模板作为叶子模块的优势不复存在。

    :return: 配置模板的模块名列表，核心配置排在最前。
    """
    import bots
    import modules

    names = ["core.config.base"]
    for package in (bots, modules):
        package_path = Path(package.__path__[0])
        for submodule in pkgutil.iter_modules(package.__path__):
            if (package_path / submodule.name / "config.py").exists():
                names.append(f"{package.__name__}.{submodule.name}.config")
    return names


def scan_config_templates() -> list[str]:
    """导入全部配置模板，补全配置文件中缺失的键。

    扫描不区分 bot 与模块的启用状态：配置项一律补全，否则用户先禁用再启用便会撞上缺键。

    :return: 加载失败的配置模板模块名列表，空列表表示全部成功。
    """
    failed = []
    for module_name in iter_config_template_modules():
        try:
            importlib.import_module(module_name)
        except Exception:
            failed.append(module_name)
            logger.exception(f"[Config] Failed to load config template {module_name}: ")
    CFGManager.save()
    return failed
