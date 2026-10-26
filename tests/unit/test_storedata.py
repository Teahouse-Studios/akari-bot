"""core.utils.storedata 单元测试 - 存储工具（需要数据库）。"""

from core.tester import func_case, Tester
from core.utils.storedata import get_stored_list, update_stored_list


async def _test_get_stored_list_empty():
    try:
        result = await get_stored_list("TEST", "nonexistent_key")
        return result == []
    except Exception:
        return False


async def _test_update_and_get_stored_list():
    try:
        test_data = [{"name": "test", "value": 123}]
        await update_stored_list("TEST", "test_key", test_data)
        result = await get_stored_list("TEST", "test_key")
        if result != test_data:
            return False

        new_data = [{"name": "updated", "value": 456}]
        await update_stored_list("TEST", "test_key", new_data)
        result = await get_stored_list("TEST", "test_key")
        if result != new_data:
            return False

        return True
    except Exception:
        return False


@func_case
async def test_storedata(tester: Tester):
    """core.utils.storedata: 存储工具测试"""
    await tester.test(_test_get_stored_list_empty, "get_stored_list() 空数据测试")
    await tester.test(_test_update_and_get_stored_list, "update_stored_list() 和 get_stored_list() 测试")

    return tester
