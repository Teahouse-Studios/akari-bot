from core.config import Config
from core.constants.default import (
    confirm_command_default,
    command_prefix_default,
)


def unique_keep_order(seq):
    return list(dict.fromkeys(seq))


confirm_command = unique_keep_order(
    filter(str.strip, Config("confirm_command", confirm_command_default))
    or confirm_command_default
) + ["⭐", "✅", "⭕"]  # 确认词

confirm_command = unique_keep_order(confirm_command)

command_prefix = unique_keep_order(
    filter(str.strip, Config("command_prefix", command_prefix_default))
    or command_prefix_default
)  # 命令前缀

__all__ = ["confirm_command", "command_prefix"]
