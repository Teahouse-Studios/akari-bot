from core.config import Config
from core.constants import (
    PrivateAssets,
    Secret,
    confirm_command_default,
    command_prefix_default,
)

confirm_command = list(
    filter(str.strip, Config("confirm_command", confirm_command_default))
    or confirm_command_default
)  # 确认指令
command_prefix = list(
    filter(str.strip, Config("command_prefix", command_prefix_default))
    or command_prefix_default
)  # 消息前缀


__all__ = ["confirm_command", "command_prefix", "PrivateAssets", "Secret"]
