"""core.utils.cache 纯函数单元测试 - 缓存工具。"""

import re

from core.tester import func_case, Tester
from core.utils.cache import random_cache_path


def _test_random_cache_path_no_ext():
    """测试 random_cache_path() - 无扩展名"""
    try:
        path = random_cache_path()
        if path is None:
            return False
        filename = path.name
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, filename):
            return False
        return True
    except Exception:
        return False


def _test_random_cache_path_with_ext():
    """测试 random_cache_path() - 带扩展名"""
    try:
        path = random_cache_path("png")
        if path is None:
            return False
        if not str(path).endswith(".png"):
            return False
        return True
    except Exception:
        return False


def _test_random_cache_path_unique():
    """测试 random_cache_path() - 每次调用返回不同路径"""
    try:
        paths = set()
        for _ in range(10):
            path = random_cache_path()
            paths.add(str(path))
        if len(paths) != 10:
            return False
        return True
    except Exception:
        return False


@func_case
async def test_cache(tester: Tester):
    """core.utils.cache: 缓存工具测试"""
    await tester.test(_test_random_cache_path_no_ext, "random_cache_path() 无扩展名测试")
    await tester.test(_test_random_cache_path_with_ext, "random_cache_path() 带扩展名测试")
    await tester.test(_test_random_cache_path_unique, "random_cache_path() 唯一性测试")

    return tester
