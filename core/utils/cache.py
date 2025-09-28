import uuid
from pathlib import Path

from core.constants.path import cache_path


def random_cache_path(ftt: str = "") -> Path:
    """
    提供带有随机UUID文件名的缓存路径。
    """
    if ftt:
        return cache_path / f"{str(uuid.uuid4())}.{ftt}"
    return cache_path / f"{str(uuid.uuid4())}"


__all__ = ["random_cache_path"]
