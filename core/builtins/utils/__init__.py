from config import Config
from core.types import PrivateAssets, Secret

if not (confirm_command := Config('confirm_command')):
    confirm_command = ["是", "对", "對", "yes", "Yes", "YES", "y", "Y"]

if not (command_prefix := Config('command_prefix')):
    command_prefix = ['~', '～']  # 消息前缀


class EnableDirtyWordCheck:
    status = False


__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
