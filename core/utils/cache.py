import uuid
from os.path import join

from core.constants.path import cache_path


def random_cache_path(ftt: str = "") -> str:
    """
    提供带有随机UUID文件名的缓存路径。
    """
    if ftt:
        return join(cache_path, f"{str(uuid.uuid4())}.{ftt}")
    return join(cache_path, f"{str(uuid.uuid4())}")


__all__ = ["random_cache_path"]
