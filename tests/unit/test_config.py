"""core.config 配置系统单元测试。"""

from unittest.mock import patch, MagicMock

from core.config import CFGManager, Config
from core.config.base import CoreConfig, CoreSecretConfig
from core.tester import func_case, Tester, mock_config


def _test_config_passthrough():
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "test_value"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("key", "default")
        return result == "test_value"


def _test_config_get_called_with_args():
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
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "example.com/path"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("api_url", get_url=True)
        return result.startswith("http://") and result.endswith("/")


def _test_config_get_url_no_slash():
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = "https://example.com/path"
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("api_url", get_url=True)
        return result == "https://example.com/path/"


def _test_config_get_url_none():
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = None
    import core.config as config_module

    with patch.object(config_module, "CFGManager", mock_cfg):
        result = config_module.Config("url", get_url=True)
        return result is None


def _test_mock_config_overrides_and_restores():
    original = CoreConfig.enable_petal
    with mock_config(CoreConfig, enable_petal=not original):
        attribute = CoreConfig.enable_petal
        direct = CFGManager.get("enable_petal", table_name="config")
    return attribute is (not original) and direct is (not original) and CoreConfig.enable_petal is original


def _test_mock_config_nested_scopes_restore_outer():
    original = CoreConfig.use_emote
    with mock_config(CoreConfig, use_emote=not original):
        with mock_config(CoreConfig, use_emote=original):
            inner = CoreConfig.use_emote
        outer = CoreConfig.use_emote
    return inner is original and outer is (not original) and CoreConfig.use_emote is original


def _test_mock_config_separates_secret_table():
    mocked = "http://127.0.0.1:7890"
    with mock_config(CoreSecretConfig, proxy=mocked):
        secret = Config("proxy", secret=True)
        plain = Config("proxy")
    return secret == mocked and plain != mocked


def _test_mock_config_rejects_unknown_field():
    original = CoreConfig.use_emote
    try:
        with mock_config(CoreConfig, no_such_field=True):
            return False
    except AttributeError:
        return CoreConfig.use_emote is original


@func_case
async def test_config(tester: Tester):
    """core.config: Config 函数测试"""
    await tester.test(_test_config_passthrough, "Config 值透传测试")
    await tester.test(_test_config_get_called_with_args, "Config 参数传递测试")
    await tester.test(_test_config_get_url_branch, "Config get_url 分支测试")
    await tester.test(_test_config_get_url_no_slash, "Config get_url 尾部斜杠测试")
    await tester.test(_test_config_get_url_none, "Config get_url None 测试")
    return tester


@func_case
async def test_mock_config(tester: Tester):
    """core.tester.mock.config: 配置项替身测试"""
    await tester.test(_test_mock_config_overrides_and_restores, "覆盖配置项并在退出后恢复原值")
    await tester.test(_test_mock_config_nested_scopes_restore_outer, "嵌套覆盖退出后恢复外层取值")
    await tester.test(_test_mock_config_separates_secret_table, "同名配置项按表与密钥标志区分")
    await tester.test(_test_mock_config_rejects_unknown_field, "未声明的配置项立即报错且不改动读取")
    return tester
