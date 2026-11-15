"""core.config 配置系统单元测试。"""

from typing import Any

from core.builtins.config import Config, use_source
from core.config.core import CoreConfig, CoreSecretConfig
from core.tester import func_case, Tester, mock_config


class _StubSource:
    """只记录取值参数的配置来源替身。"""

    readonly = False

    def __init__(self, value: Any):
        self.value = value
        self.queries: list[tuple] = []

    def has(self, q: str, secret: bool = False, table_name: str | None = None) -> bool:
        return False

    def get(
        self,
        q: str,
        default: Any = None,
        cfg_type: type | tuple | None = None,
        secret: bool = False,
        table_name: str | None = None,
        _global: bool = False,
        _generate: bool = False,
        standalone_comment_keys: tuple[str, ...] = (),
    ) -> Any:
        self.queries.append((q, default, cfg_type, secret, table_name))
        return self.value

    def write(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("Config() must not write.")

    def delete(self, q: str, table_name: str | None = None) -> bool:
        return False


def _test_config_passthrough():
    with use_source(_StubSource("test_value")):
        return Config("key", "default") == "test_value"


def _test_config_get_called_with_args():
    source = _StubSource("v")
    with use_source(source):
        Config("mykey", "mydefault", cfg_type=str, secret=True, table_name="module_test")
        q, default, cfg_type, secret, table_name = source.queries[0]
    return (
        q == "mykey" and default == "mydefault" and cfg_type is str and secret is True and table_name == "module_test"
    )


def _test_config_get_url_branch():
    with use_source(_StubSource("example.com/path")):
        return Config("api_url", get_url=True) == "http://example.com/path/"


def _test_config_get_url_no_slash():
    with use_source(_StubSource("https://example.com/path")):
        return Config("api_url", get_url=True) == "https://example.com/path/"


def _test_config_get_url_none():
    with use_source(_StubSource(None)):
        return Config("url", get_url=True) is None


def _test_mock_config_overrides_and_restores():
    original = CoreConfig.enable_petal
    with mock_config(CoreConfig, enable_petal=not original):
        attribute = CoreConfig.enable_petal
        direct = Config("enable_petal", table_name="config")
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
