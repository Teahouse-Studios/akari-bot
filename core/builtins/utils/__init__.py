from core.config import config
from core.constants import PrivateAssets, Secret, confirm_command, command_prefix

confirm_command = config('confirm_command', confirm_command)  # 确认指令
command_prefix = config('command_prefix', command_prefix)  # 指令前缀


__all__ = ["confirm_command", "command_prefix", "PrivateAssets", "Secret"]
