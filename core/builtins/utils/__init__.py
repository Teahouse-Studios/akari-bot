from core.config import Config
from core.constants import PrivateAssets, Secret, confirm_command, command_prefix

confirm_command = filter(str.strip, Config('confirm_command',
                         default_confirm_command)) or default_confirm_command  # 确认指令
command_prefix = filter(str.strip, Config('confirm_command',
                        default_command_prefix)) or default_command_prefix  # 消息前缀


__all__ = ["confirm_command", "command_prefix", "PrivateAssets", "Secret"]
