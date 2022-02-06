import os
import traceback
from configparser import ConfigParser
from os.path import abspath

import requests

from core.exceptions import ConfigFileNotFound
from core.logger import Logger

confirm_command = ["是", "对", '确定', '是吧', '大概是',
                   '也许', '可能', '对的', '是呢', '对呢', '嗯', '嗯呢',
                   '吼啊', '资瓷', '是呗', '也许吧', '对呗', '应该',
                   'yes', 'y', 'yeah', 'yep', 'ok', 'okay', '⭐', '√']

command_prefix = ['~', '～']  # 消息前缀


class EnableDirtyWordCheck:
    status = False


class PrivateAssets:
    path = os.path.abspath('.')

    @staticmethod
    def set(path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.mkdir(path)
        PrivateAssets.path = path


class Secret:
    list = []

    @staticmethod
    def add(secret):
        Secret.list.append(secret)


class ErrorMessage:
    def __init__(self, error_message):
        self.error_message = '发生错误：' + error_message \
                             + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=report_bug.yaml&title=%5BBUG%5D%3A+'

    def __str__(self):
        return self.error_message

    def __repr__(self):
        return self.error_message


def load_secret():
    config_filename = 'config.cfg'
    config_path = abspath('./config/' + config_filename)
    cp = ConfigParser()
    cp.read(config_path)
    section = cp.sections()
    if len(section) == 0:
        raise ConfigFileNotFound(config_path) from None
    section = section[0]
    options = cp.options(section)
    for option in options:
        value = cp.get(section, option)
        if value.upper() not in ['', 'TRUE', 'FALSE']:
            Secret.add(value.upper())
    try:
        ip = requests.get('https://api.ip.sb/ip', timeout=10)
        if ip:
            Secret.add(ip.text.replace('\n', ''))
    except:
        Logger.error(traceback.format_exc())
        pass


load_secret()

__all__ = ["confirm_command", "command_prefix", "EnableDirtyWordCheck", "PrivateAssets", "Secret", "ErrorMessage"]
