import os

from .message import *
from .module import *
from .command import *


class PrivateAssets:
    path = os.path.abspath('assets/private/default')
    if not os.path.exists(path):
        os.makedirs(path)

    @classmethod
    def set(cls, path):
        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        cls.path = path


class Secret:
    list = []

    @classmethod
    def add(cls, secret):
        cls.list.append(secret)
