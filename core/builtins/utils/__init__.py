import os
from config import Config

if not (confirm_command := Config('confirm_command')):
    confirm_command = ["是", "对", "對", "yes", "Yes", "YES", "y", "Y"]

if not (command_prefix := Config('command_prefix')):
    command_prefix = ['~', '～']  # 消息前缀


class EnableDirtyWordCheck:
    status = False


class PrivateAssets:
    path = os.path.abspath('.')

    @classmethod
    def set(cls, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.mkdir(path)
        cls.path = path


class Secret:
    list = []

    @classmethod
    def add(cls, secret):
        cls.list.append(secret)


__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret"]
