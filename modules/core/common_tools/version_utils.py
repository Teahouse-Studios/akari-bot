"""公共版本展示辅助。"""

from core.builtins.bot import Bot


def get_version_display() -> str | None:
    """返回面向用户展示的版本号；未知版本时返回 None。"""
    if not Bot.Info.version:
        return None
    version = str(Bot.Info.version)
    return version[4:11] if version.startswith("git:") else version
