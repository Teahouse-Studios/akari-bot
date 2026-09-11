"""各进程内存占用汇总的单元测试 - 指标口径、peer 名还原与失败可见性。

``uss`` 仅自测可得，故 ``build_usage`` 须显式区分两种口径，避免展示层混算。未回包或
回包无效的进程同样须出现在结果中，否则无法与进程未启动相区分。
"""

import os

from core.queue.diagnostics import (
    build_usage,
    collect_external_usage,
    collect_self_usage,
    REASON_MAX_LENGTH,
    summarize_process_usage,
)
from core.tester import func_case, Tester


def _test_build_usage_prefers_uss():
    """测试同时存在 uss 与 rss 时取 uss"""
    usage = build_usage("QQ", {"pid": 42, "rss": 200, "uss": 100, "threads": 7})
    if usage is None:
        return False
    return usage.memory == 100 and usage.metric == "USS" and usage.pid == 42 and usage.threads == 7


def _test_build_usage_falls_back_to_rss():
    """测试缺少 uss 时回落至 rss 并标记口径"""
    usage = build_usage("daemon", {"pid": 42, "rss": 200})
    if usage is None:
        return False
    return usage.memory == 200 and usage.metric == "RSS" and usage.threads is None


def _test_build_usage_rejects_empty_payload():
    """测试两种指标都缺失时视为无效载荷"""
    return build_usage("QQ", {"pid": 42}) is None and build_usage("QQ", {}) is None


def _test_build_usage_rejects_non_integer_metrics():
    """测试非整数指标不视为有效数值"""
    if build_usage("QQ", {"rss": "200"}) is not None:
        return False
    usage = build_usage("QQ", {"uss": None, "rss": 200})
    return usage is not None and usage.metric == "RSS"


def _test_summarize_resolves_service_names():
    """测试 peer_id 按 Alive 快照还原为 service 名并排序"""
    usages, failures = summarize_process_usage(
        results={
            "Internal|b": [{"pid": 2, "rss": 20, "uss": 10}],
            "Internal|a": [{"pid": 1, "rss": 40, "uss": 30}],
        },
        errors={},
        peers={
            "Internal|a": {"service": "Server"},
            "Internal|b": {"service": "QQ"},
        },
    )
    if failures:
        return False
    return [usage.name for usage in usages] == ["QQ", "Server"]


def _test_summarize_falls_back_to_peer_id():
    """测试快照缺失该实例时退回 peer_id"""
    usages, _ = summarize_process_usage(
        results={"Internal|c": [{"pid": 3, "rss": 30}]},
        errors={},
        peers={},
    )
    return len(usages) == 1 and usages[0].name == "Internal|c"


def _test_summarize_reports_errors():
    """测试未回包的实例列入失败列表并附带原因"""
    usages, failures = summarize_process_usage(
        results={},
        errors={"Internal|d": "timeout"},
        peers={"Internal|d": {"service": "Discord"}},
    )
    if usages:
        return False
    return len(failures) == 1 and failures[0].name == "Discord" and failures[0].reason == "timeout"


def _test_summarize_reports_invalid_payload():
    """测试已回包但载荷无效时仍然可见"""
    usages, failures = summarize_process_usage(
        results={"Internal|e": [{"pid": 5}]},
        errors={},
        peers={"Internal|e": {"service": "Telegram"}},
    )
    if usages:
        return False
    return len(failures) == 1 and failures[0].name == "Telegram" and failures[0].reason == "invalid"


def _test_summarize_skips_non_dict_values():
    """测试混入非字典返回值时取有效载荷"""
    usages, failures = summarize_process_usage(
        results={"Internal|f": [None, {"pid": 6, "rss": 60}]},
        errors={},
        peers={"Internal|f": {"service": "Matrix"}},
    )
    return not failures and len(usages) == 1 and usages[0].memory == 60


def _test_summarize_truncates_reason():
    """测试远端异常消息被截断"""
    _, failures = summarize_process_usage(
        results={},
        errors={"Internal|g": "x" * 500},
        peers={},
    )
    return len(failures) == 1 and len(failures[0].reason) == REASON_MAX_LENGTH


def _test_collect_self_usage_reports_own_pid():
    """测试自测指标包含本进程 PID 与 rss"""
    usage = collect_self_usage()
    if usage.get("pid") != os.getpid():
        return False
    return isinstance(usage.get("rss"), int) and usage["rss"] > 0


def _test_collect_external_usage_handles_missing_pid():
    """测试 PID 缺失或进程不存在时返回 None"""
    if collect_external_usage(None) is not None:
        return False
    if collect_external_usage(0) is not None:
        return False
    # 该取值超出 PID 上限，不对应任何进程。
    return collect_external_usage(2**31 - 1) is None


def _test_collect_external_usage_omits_uss():
    """测试跨进程读取仅给出 rss"""
    usage = collect_external_usage(os.getpid())
    if usage is None:
        return False
    return "uss" not in usage and isinstance(usage.get("rss"), int)


@func_case
async def test_process_usage_metrics(tester: Tester):
    """core.queue.diagnostics: 内存指标口径测试"""
    await tester.test(_test_build_usage_prefers_uss, "优先取 uss 测试")
    await tester.test(_test_build_usage_falls_back_to_rss, "回落 rss 测试")
    await tester.test(_test_build_usage_rejects_empty_payload, "空载荷无效测试")
    await tester.test(_test_build_usage_rejects_non_integer_metrics, "非整数指标无效测试")

    return tester


@func_case
async def test_process_usage_summary(tester: Tester):
    """core.queue.diagnostics: 逐实例结果汇总测试"""
    await tester.test(_test_summarize_resolves_service_names, "service 名还原与排序测试")
    await tester.test(_test_summarize_falls_back_to_peer_id, "快照缺失回退 peer_id 测试")
    await tester.test(_test_summarize_reports_errors, "未回包实例可见测试")
    await tester.test(_test_summarize_reports_invalid_payload, "无效载荷可见测试")
    await tester.test(_test_summarize_skips_non_dict_values, "跳过非字典返回值测试")
    await tester.test(_test_summarize_truncates_reason, "失败原因截断测试")

    return tester


@func_case
async def test_process_usage_collection(tester: Tester):
    """core.queue.diagnostics: 进程指标采集测试"""
    await tester.test(_test_collect_self_usage_reports_own_pid, "自测本进程指标测试")
    await tester.test(_test_collect_external_usage_handles_missing_pid, "缺失进程降级测试")
    await tester.test(_test_collect_external_usage_omits_uss, "跨进程不取 uss 测试")

    return tester
