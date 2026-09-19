"""core.builtins.parser.message 单元测试 - 正则平台筛选与执行锁。"""

import re
from copy import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.builtins.parser.message import (
    LONG_REGEX_MESSAGE_LENGTH,
    _confirm_long_regex_message,
    regex_func_available,
    try_acquire_execution_lock,
)
from core.tester import func_case, Tester


def _fake_lock_msg(sender_id: str):
    """构造一个仅提供 sender_id 的会话替身，执行锁只读取该字段。"""
    return SimpleNamespace(
        session_info=SimpleNamespace(
            sender_id=sender_id,
            sender_union_id=None,
            tmp={},
        )
    )


async def _test_lock_acquired_once():
    """测试执行锁 - 首次获取成功，重复获取失败"""
    try:
        from core.builtins.session.lock import ExecutionLockList

        msg = _fake_lock_msg("LOCKTEST|once")
        first = await try_acquire_execution_lock(msg)
        second = await try_acquire_execution_lock(msg)
        ExecutionLockList.remove(msg)
        return first and not second

    except Exception:
        return False


async def _test_lock_released_can_reacquire():
    """测试执行锁 - 释放后可以重新获取"""
    try:
        from core.builtins.session.lock import ExecutionLockList

        msg = _fake_lock_msg("LOCKTEST|again")
        await try_acquire_execution_lock(msg)
        ExecutionLockList.remove(msg)
        reacquired = await try_acquire_execution_lock(msg)
        ExecutionLockList.remove(msg)
        return reacquired

    except Exception:
        return False


def _fake_avail_rfunc(available_for=None, exclude_from=None, load: bool = True):
    """构造一条仅含平台声明的正则处理函数替身。"""
    return SimpleNamespace(
        available_for=available_for if available_for is not None else ["*"],
        exclude_from=exclude_from if exclude_from is not None else [],
        load=load,
    )


def _fake_long_regex_message(pattern: str, text: str, *, skip_long_message_confirm: bool = False):
    rfunc = SimpleNamespace(
        available_for=["*"],
        exclude_from=[],
        load=True,
        mode="M",
        compiled=re.compile(pattern),
        text_only=True,
        element_filter=[],
        trigger_once_startup=False,
        skip_long_message_confirm=skip_long_message_confirm,
    )
    module = SimpleNamespace(
        _db_load=True,
        regex=True,
        base=False,
        load=True,
        available_for=["*"],
        exclude_from=[],
        regex_list=SimpleNamespace(set=[rfunc]),
    )
    msg = SimpleNamespace(
        trigger_msg=text,
        session_info=SimpleNamespace(
            enabled_modules=["test"],
            read_all_messages=True,
            target_from="TEST",
            client_name="TEST",
            target_id="TEST|0",
        ),
        as_display=lambda **_: text,
        wait_confirm=AsyncMock(return_value=False),
    )
    return msg, {"test": module}


async def _test_long_regex_match_requests_confirmation():
    msg, modules = _fake_long_regex_message("触发", "触发" + "x" * 100)
    result = await _confirm_long_regex_message(msg, modules)
    return (
        not result
        and msg.wait_confirm.await_count == 1
        and msg.wait_confirm.await_args.kwargs.get("consume_any_message") is True
    )


async def _test_long_regex_confirmation_allows_parsing():
    msg, modules = _fake_long_regex_message("触发", "触发" + "x" * 100)
    msg.wait_confirm.return_value = True
    result = await _confirm_long_regex_message(msg, modules)
    return result and msg.wait_confirm.await_count == 1


async def _test_long_regex_miss_does_not_request_confirmation():
    msg, modules = _fake_long_regex_message("未命中", "触发" + "x" * 100)
    result = await _confirm_long_regex_message(msg, modules)
    return result and msg.wait_confirm.await_count == 0


async def _test_short_regex_match_does_not_request_confirmation():
    msg, modules = _fake_long_regex_message("触发", "触发")
    result = await _confirm_long_regex_message(msg, modules)
    return result and msg.wait_confirm.await_count == 0


async def _test_length_threshold_is_75_characters():
    pattern = "触发"
    exact_msg, exact_modules = _fake_long_regex_message(
        pattern, pattern + "x" * (LONG_REGEX_MESSAGE_LENGTH - len(pattern))
    )
    over_msg, over_modules = _fake_long_regex_message(
        pattern, pattern + "x" * (LONG_REGEX_MESSAGE_LENGTH + 1 - len(pattern))
    )
    exact_result = await _confirm_long_regex_message(exact_msg, exact_modules)
    over_result = await _confirm_long_regex_message(over_msg, over_modules)
    return exact_result and exact_msg.wait_confirm.await_count == 0 and not over_result


async def _test_long_message_exempt_regex_skips_confirmation():
    msg, modules = _fake_long_regex_message(
        "https://example.com/", "https://example.com/" + "x" * 100, skip_long_message_confirm=True
    )
    result = await _confirm_long_regex_message(msg, modules)
    return result and msg.wait_confirm.await_count == 0


async def _test_long_message_still_confirms_for_non_exempt_regex():
    msg, modules = _fake_long_regex_message(
        "https://example.com/", "https://example.com/" + "x" * 100, skip_long_message_confirm=True
    )
    regular_rfunc = copy(modules["test"].regex_list.set[0])
    regular_rfunc.mode = "A"
    regular_rfunc.compiled = re.compile("x+")
    regular_rfunc.skip_long_message_confirm = False
    modules["test"].regex_list.set.append(regular_rfunc)
    result = await _confirm_long_regex_message(msg, modules)
    return not result and msg.wait_confirm.await_count == 1


async def _test_wildcard_available_everywhere():
    """测试正则平台过滤 - 默认通配对任何平台可用"""
    try:
        return regex_func_available(_fake_avail_rfunc(), "QQ|Group", "QQ")

    except Exception:
        return False


async def _test_available_for_restricts_platform():
    """测试正则平台过滤 - available_for 限定后仅命中的平台可用"""
    try:
        rfunc = _fake_avail_rfunc(available_for=["QQ"])
        hit = regex_func_available(rfunc, "QQ|Group", "QQ")
        miss = regex_func_available(rfunc, "QQBot|Group", "QQBot")
        return hit and not miss

    except Exception:
        return False


async def _test_available_for_empty_blocks_all():
    """测试正则平台过滤 - available_for 为空列表时对任何平台都不可用"""
    try:
        rfunc = _fake_avail_rfunc(available_for=[])
        return not regex_func_available(rfunc, "QQ|Group", "QQ") and not regex_func_available(
            rfunc, "QQBot|Group", "QQBot"
        )

    except Exception:
        return False


async def _test_exclude_from_takes_precedence():
    """测试正则平台过滤 - exclude_from 优先于 available_for"""
    try:
        rfunc = _fake_avail_rfunc(available_for=["*"], exclude_from=["QQ"])
        return not regex_func_available(rfunc, "QQ|Group", "QQ") and regex_func_available(rfunc, "QQBot|Group", "QQBot")

    except Exception:
        return False


async def _test_target_from_also_matches():
    """测试正则平台过滤 - 场景前缀与客户端名任一命中即可用"""
    try:
        rfunc = _fake_avail_rfunc(available_for=["QQ|Group"])
        hit = regex_func_available(rfunc, "QQ|Group", "QQ")
        miss = regex_func_available(rfunc, "QQ|Private", "QQ")
        return hit and not miss

    except Exception:
        return False


async def _test_unloaded_is_unavailable():
    """测试正则平台过滤 - 未加载的正则一律不可用"""
    try:
        return not regex_func_available(_fake_avail_rfunc(load=False), "QQ|Group", "QQ")

    except Exception:
        return False


@func_case
async def test_regex_filter_order(tester: Tester):
    """core.builtins.parser.message: 正则平台筛选与执行锁测试"""
    await tester.test(_test_lock_acquired_once, "执行锁互斥测试")
    await tester.test(_test_lock_released_can_reacquire, "执行锁释放后重取测试")
    await tester.test(_test_wildcard_available_everywhere, "通配平台可用测试")
    await tester.test(_test_available_for_restricts_platform, "平台限定测试")
    await tester.test(_test_available_for_empty_blocks_all, "空列表全禁测试")
    await tester.test(_test_exclude_from_takes_precedence, "排除优先测试")
    await tester.test(_test_target_from_also_matches, "场景前缀匹配测试")
    await tester.test(_test_unloaded_is_unavailable, "未加载不可用测试")
    await tester.test(_test_long_regex_match_requests_confirmation, "长消息命中正则时请求确认")
    await tester.test(_test_long_regex_confirmation_allows_parsing, "确认继续后允许正则解析")
    await tester.test(_test_long_regex_miss_does_not_request_confirmation, "长消息未命中正则时不请求确认")
    await tester.test(_test_short_regex_match_does_not_request_confirmation, "短消息不请求确认")
    await tester.test(_test_length_threshold_is_75_characters, "75 字及以下不请求确认，76 字触发确认")
    await tester.test(_test_long_message_exempt_regex_skips_confirmation, "豁免正则命中长消息时跳过确认")
    await tester.test(_test_long_message_still_confirms_for_non_exempt_regex, "其它正则命中时仍请求确认")

    return tester
