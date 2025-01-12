import uuid
from os.path import join

from core.constants.path import cache_path


def random_cache_path() -> str:
    """
    提供带有随机UUID文件名的缓存路径。
    """
    return join(cache_path, str(uuid.uuid4()))


__all__ = ["random_cache_path"]
