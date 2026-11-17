"""配置初始化入口。

配置的加载与迁移只在明确调用时执行。
"""

from core.builtins.config.manager import CFGManager


def bootstrap_config() -> None:
    """加载配置文件；非只读进程先执行版本迁移。

    须在导入任何配置模板之前调用，重复调用无副作用。
    """
    if CFGManager.is_loaded():
        return
    if not CFGManager.readonly:
        import core.builtins.config.update  # noqa: F401  迁移在导入期执行
    CFGManager.load()


def bootstrap_writable_config() -> list[str]:
    """迁移、加载并补全缺失的配置项。

    :return: 加载失败的配置模板模块名，空列表表示全部成功。
    """
    from core.builtins.config.scan import scan_config_templates

    bootstrap_config()
    return scan_config_templates()


__all__ = ["bootstrap_config", "bootstrap_writable_config"]
