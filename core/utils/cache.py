import uuid
from os.path import abspath

from config import Config


def random_cache_path():
    return abspath(f'{Config("cache_path", "./cache/")}/{str(uuid.uuid4())}')


__all__ = ['random_cache_path']
