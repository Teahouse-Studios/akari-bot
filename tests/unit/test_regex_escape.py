"""消息正则解析临时关闭功能测试。"""

from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.config.base import CoreConfig
from core.tester import func_case, Tester


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
    await tester.test(_test_production_parser_skips_markers, "生产解析器在正则执行前跳过句号消息")
    await tester.test(_test_production_parser_keeps_normal_regex_parsing, "生产解析器保留普通消息正则解析")
    await tester.test(_test_production_parser_uses_configured_markers, "生产解析器使用配置的正则关闭前缀")
    await tester.test(_test_production_parser_allows_empty_marker_config, "生产解析器允许空正则关闭前缀")
    return tester
