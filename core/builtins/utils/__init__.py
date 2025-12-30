from core.config import Config
from core.constants.default import (
    confirm_command_default,
    command_prefix_default,
)
from core.utils.tools import unique_list


confirm_command = unique_list(
    filter(str.strip, Config("confirm_command", confirm_command_default))
    or confirm_command_default
) + ["⭐", "✅", "⭕"]  # 确认词

command_prefix = unique_list(
    filter(str.strip, Config("command_prefix", command_prefix_default))
    or command_prefix_default
)  # 命令前缀

__all__ = ["confirm_command", "command_prefix"]
