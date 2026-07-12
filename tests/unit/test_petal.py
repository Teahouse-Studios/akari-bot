"""core.utils.petal 单元测试 - 花瓣系统（需要数据库/配置）。"""

from unittest.mock import patch

from core.tester import func_case, Tester
from core.tester.mock.factory import TestDataFactory
from core.tester.mock.session import MockMessageSession


async def _test_petal_functions_no_throw():
    """测试花瓣函数 - 不抛出异常"""
    try:
        from core.utils.petal import gained_petal, lost_petal, cost_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        await gained_petal(msg, 10)
        await lost_petal(msg, 10)
        await cost_petal(msg, 10, send_prompt=False)

        return True
    except Exception:
        return False


async def _test_cost_petal_returns_bool():
    """测试 cost_petal - 返回布尔值"""
    try:
        from core.utils.petal import cost_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        result = await cost_petal(msg, 10, send_prompt=False)
        if not isinstance(result, bool):
            return False

        return True
    except Exception:
        return False


async def _test_gained_petal_with_mock():
    """测试 gained_petal - Mock Config 启用花瓣系统"""
    try:
        from core.utils.petal import gained_petal

        await TestDataFactory.setup_default_test_env()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        def mock_config(key, default=None):
            config_map = {
                "enable_petal": True,
                "enable_get_petal": True,
                "petal_gained_limit": 100,
            }
            return config_map.get(key, default)

        with patch("core.utils.petal.Config", side_effect=mock_config):
            result = await gained_petal(msg, 10)
            if result is None:
                return False

        return True
    except Exception:
        return False


async def _test_cost_petal_insufficient_with_mock():
    """测试 cost_petal - 花瓣不足时返回 False"""
    try:
        from core.utils.petal import cost_petal

        await TestDataFactory.ensure_sender(petal=0)
        msg = MockMessageSession("~test")
        await msg.async_init("~test")

        def mock_config(key, default=None):
            config_map = {
                "enable_petal": True,
            }
            return config_map.get(key, default)

        with patch("core.utils.petal.Config", side_effect=mock_config):
            result = await cost_petal(msg, 100, send_prompt=False)
            if result is not False:
                return False

        return True
    except Exception:
        return False


@func_case
async def test_petal(tester: Tester):
    """core.utils.petal: 花瓣系统测试"""
    await tester.test(_test_petal_functions_no_throw, "花瓣函数不抛异常测试")
    await tester.test(_test_cost_petal_returns_bool, "cost_petal 返回布尔值测试")
    await tester.test(_test_gained_petal_with_mock, "gained_petal Mock Config 测试")
    await tester.test(_test_cost_petal_insufficient_with_mock, "cost_petal 花瓣不足 Mock 测试")

    return tester
