from config import Config
from core.types import PrivateAssets, Secret


confirm_command = Config('confirm_command', default=["是", "对", "對", "yes", "Yes", "YES", "y", "Y"])
command_prefix = Config('command_prefix', default=['~', '～'])  # 消息前缀


class EnableDirtyWordCheck:
    status = False


__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
