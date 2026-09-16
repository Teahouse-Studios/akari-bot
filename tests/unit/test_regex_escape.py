"""消息正则解析临时关闭功能测试。"""

from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.config.base import CoreConfig
from core.constants.default import regex_disable_prefix_default
from core.tester import func_case, Tester
from core.tester.mock.parser import parser as mock_parser
from core.tester.mock.session import MockMessageSession


def _test_default_from_constants():
    field = CoreConfig.__config_fields__["regex_disable_prefix"]
    return regex_disable_prefix_default == [".", "。"] and field["default"] == regex_disable_prefix_default


async def _regex_called(input_: str) -> bool:
    msg = MockMessageSession(input_, is_ci=True)
    await msg.async_init(input_)
    execute_regex = AsyncMock()
    with patch("core.tester.mock.parser._execute_regex", execute_regex):
        await mock_parser(msg)
    return execute_regex.await_count == 1


async def _test_mock_parser_skips_halfwidth_marker():
    return not await _regex_called(".BV1xx411c7mD")


async def _test_mock_parser_skips_fullwidth_marker():
    return not await _regex_called("。BV1xx411c7mD")


async def _test_mock_parser_keeps_normal_regex_parsing():
    return await _regex_called("BV1xx411c7mD")


async def _production_regex_called(input_: str) -> bool:
    from core.builtins.parser.message import parser

    session_info = await SessionInfo.assign(
        target_id="REGEXESCAPE|Group|0",
        target_from="REGEXESCAPE|Group",
        client_name="REGEXESCAPE",
        sender_id="REGEXESCAPE|0",
        messages=MessageChain.assign(Plain(input_)),
        create=True,
    )
    msg = MessageSession(session_info=session_info)
    execute_regex = AsyncMock()
    with patch("core.builtins.parser.message._execute_regex", execute_regex):
        await parser(msg)
    return execute_regex.await_count == 1


async def _test_production_parser_skips_markers():
    return not await _production_regex_called(".BV1xx411c7mD") and not await _production_regex_called("。BV1xx411c7mD")


async def _test_production_parser_keeps_normal_regex_parsing():
    return await _production_regex_called("BV1xx411c7mD")


async def _test_production_parser_uses_configured_markers():
    with patch.object(CoreConfig, "regex_disable_prefix", ["!"]):
        return not await _production_regex_called("!BV1xx411c7mD") and await _production_regex_called(".BV1xx411c7mD")


async def _test_production_parser_allows_empty_marker_config():
    with patch.object(CoreConfig, "regex_disable_prefix", []):
        return await _production_regex_called(".BV1xx411c7mD")


@func_case
async def test_regex_escape(tester: Tester):
    await tester.test(_test_default_from_constants, "默认前缀由 core.constants 提供并绑定至 CoreConfig")
    await tester.test(_test_mock_parser_skips_halfwidth_marker, "测试解析器跳过半角句号消息")
    await tester.test(_test_mock_parser_skips_fullwidth_marker, "测试解析器跳过全角句号消息")
    await tester.test(_test_mock_parser_keeps_normal_regex_parsing, "普通消息继续执行正则解析")
    await tester.test(_test_production_parser_skips_markers, "生产解析器在正则执行前跳过句号消息")
    await tester.test(_test_production_parser_keeps_normal_regex_parsing, "生产解析器保留普通消息正则解析")
    await tester.test(_test_production_parser_uses_configured_markers, "生产解析器使用配置的正则关闭前缀")
    await tester.test(_test_production_parser_allows_empty_marker_config, "生产解析器允许空正则关闭前缀")
    return tester
