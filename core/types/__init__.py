import os

from core.path import assets_path
from .command import *
from .message import *
from .module import *


class PrivateAssets:
    path = os.path.join(assets_path, 'private', 'default')
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
