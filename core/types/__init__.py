import os

from .message import *
from .module import *


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
