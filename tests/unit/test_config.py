"""core.config 配置系统单元测试。"""

from unittest.mock import patch, MagicMock

from core.tester import func_case, Tester


def _test_config_passthrough():
    """Config: 值应直接透传 CFGManager.get 的返回值"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "test_value"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("key", "default")
        return result == "test_value"


def _test_config_none_passthrough():
    """Config: CFGManager.get 返回 None 时 Config 也返回 None"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = None
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("key", "default")
        return result is None


def _test_config_get_called_with_args():
    """Config: 应将参数正确传递给 CFGManager.get"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "v"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        config_module.Config("mykey", "mydefault", cfg_type=str, secret=True, table_name="module_test")
        args, kwargs = mock_cfg.get.call_args
        return (
            args[0] == "mykey"
            and args[1] == "mydefault"
            and args[3] is True  # secret
            and args[4] == "module_test"  # table_name
        )


def _test_config_get_url_branch():
    """Config: get_url=True 时走 URL 格式化分支"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "example.com/path"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("api_url", get_url=True)
        return result.startswith("http://") and result.endswith("/")


def _test_config_get_url_no_slash():
    """Config: get_url=True 无尾部斜杠时自动添加"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "https://example.com/path"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("api_url", get_url=True)
        return result == "https://example.com/path/"


def _test_config_get_url_already_prefixed():
    """Config: get_url=True 已有协议头时不再添加"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "https://example.com"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("url", get_url=True)
        return result.startswith("https://")


def _test_config_get_url_none():
    """Config: get_url=True 值为 None 时返回 None"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = None
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("url", get_url=True)
        return result is None


def _test_config_int_passthrough():
    """Config: 整数值应正确透传"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = 42
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("count", default=0, cfg_type=int)
        return result == 42


def _test_config_bool_passthrough():
    """Config: 布尔值应正确透传"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = True
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("flag", default=False, cfg_type=bool)
        return result is True


def _test_config_list_passthrough():
    """Config: 列表值应正确透传"""
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = ["a", "b"]
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("items", default=[], cfg_type=list)
        return result == ["a", "b"]


@func_case
async def test_config(tester: Tester):
    """core.config: Config 函数测试"""
    await tester.test(_test_config_passthrough, "Config 值透传测试")
    await tester.test(_test_config_none_passthrough, "Config None 透传测试")
    await tester.test(_test_config_get_called_with_args, "Config 参数传递测试")
    await tester.test(_test_config_get_url_branch, "Config get_url 分支测试")
    await tester.test(_test_config_get_url_no_slash, "Config get_url 尾部斜杠测试")
    await tester.test(_test_config_get_url_already_prefixed, "Config get_url 已有协议头测试")
    await tester.test(_test_config_get_url_none, "Config get_url None 测试")
    await tester.test(_test_config_int_passthrough, "Config 整数透传测试")
    await tester.test(_test_config_bool_passthrough, "Config 布尔透传测试")
    await tester.test(_test_config_list_passthrough, "Config 列表透传测试")
    return tester
