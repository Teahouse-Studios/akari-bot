import uuid
from os.path import join

from core.constants.path import cache_path


def random_cache_path():
    return join(cache_path, str(uuid.uuid4()))


__all__ = ['random_cache_path']
