"""core.utils.cache 纯函数单元测试 - 缓存工具。"""

from core.tester import func_case, Tester
from core.utils.cache import random_cache_path


def _test_random_cache_path_no_ext():
    try:
        path = random_cache_path()
        return path is not None and bool(path.name) and path.suffix == ""
    except Exception:
        return False


def _test_random_cache_path_with_ext():
    try:
        path = random_cache_path("png")
        if path is None:
            return False
        if not str(path).endswith(".png"):
            return False
        return True
    except Exception:
        return False


@func_case
async def test_cache(tester: Tester):
    """core.utils.cache: 缓存工具测试"""
    await tester.test(_test_random_cache_path_no_ext, "random_cache_path() 无扩展名测试")
    await tester.test(_test_random_cache_path_with_ext, "random_cache_path() 带扩展名测试")
    return tester
