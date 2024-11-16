from core.config import Config
from core.types import PrivateAssets, Secret

default_confirm_command = ['是', '对', '對', 'yes', 'Yes', 'YES', 'y', 'Y']
default_command_prefix = ['~', '～']
confirm_command = [i for i in Config('confirm_command', default_confirm_command)
                   if i.strip()] or default_confirm_command
command_prefix = [i for i in Config('command_prefix', default_command_prefix)
                  if i.strip()] or default_command_prefix  # 消息前缀


class EnableDirtyWordCheck:
    status = False


__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
