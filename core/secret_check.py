import traceback
from configparser import ConfigParser
from os.path import abspath
from typing import Union, List

import requests

from core.elements import Plain


class Secret:
    list = []

    @staticmethod
    def add(secret):
        Secret.list.append(secret)

    @staticmethod
    def find(message: Union[str, List]):
        if isinstance(message, str):
            for secret in Secret.list:
                if message.upper().find(secret.upper()) != -1:
                    return True
        elif isinstance(message, (list, tuple)):
            for m in message:
                if isinstance(m, Plain):
                    for secret in Secret.list:
                        if m.text.upper().find(secret.upper()) != -1:
                            return True
        return False


def load_secret():
    config_filename = 'config.cfg'
    config_path = abspath('./config/' + config_filename)
    cp = ConfigParser()
    cp.read(config_path)
    section = cp.sections()[0]
    options = cp.options(section)
    for option in options:
        value = cp.get(section, option)
        if value != '':
            Secret.add(value.upper())
    try:
        ip = requests.get('https://api.ip.sb/ip', timeout=10)
        if ip:
            Secret.add(ip.text.replace('\n', ''))
    except:
        traceback.print_exc()
        pass


load_secret()
