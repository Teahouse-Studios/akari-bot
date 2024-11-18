from core.config import config
from core.types import PrivateAssets, Secret

confirm_command = config('confirm_command', ['是', '对', '對', 'yes', 'Yes', 'YES', 'y', 'Y'])  # 确认指令
command_prefix = config('command_prefix', ['~', '～'])  # 指令前缀


class EnableDirtyWordCheck:
    status = False


__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
