"""core.retired 单元测试 - 迁移关系解析、退役判定与介入点。

本文件集中放置所有改动 ``CoreConfig.retired_clients`` 的用例：``tester.py`` 并发执行各个
func_case，而该配置与 ``RETIRED_ROUTES`` 是进程级全局状态，分散在多个文件中改动会互相覆盖。
同一 func_case 内部则是串行的，因此集中于此即可避免竞争。
"""

from core.config.base import CoreConfig
from core.retired import (
    RETIRED_ALLOWED_MODULES,
    filter_retired_targets,
    is_merge_route_allowed,
    is_module_allowed_when_retired,
    is_retired_client,
    is_retired_target,
    parse_retired_routes,
    reload_retired_routes,
    should_yield_channel,
)
from core.tester import func_case, Tester


def _use_routes(entries: list):
    """临时替换迁移关系配置并重新解析，返回原值供还原。"""
    original = CoreConfig.retired_clients
    CoreConfig.retired_clients = entries
    reload_retired_routes()
    return original


def _restore_routes(original: list):
    """还原迁移关系配置并重新解析。"""
    CoreConfig.retired_clients = original
    reload_retired_routes()


async def _test_client_judgement():
    """测试退役判定 - 按客户端名判定，大小写敏感且未配置时恒为假"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["QQ -> QQBot"])
        hit = is_retired_client("QQ")
        # 目标客户端本身并未退役。
        miss = is_retired_client("QQBot")
        none_safe = not is_retired_client(None)

        _use_routes([])
        empty = not is_retired_client("QQ")

        return hit and not miss and none_safe and empty

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_target_judgement():
    """测试退役判定 - 按场景 ID 的平台前缀判定"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["QQ -> QQBot"])
        hit = is_retired_target("QQ|Group|12345")
        miss = is_retired_target("QQBot|Group|12345")
        none_safe = not is_retired_target(None)
        no_sep = not is_retired_target("QQ")
        return hit and not miss and none_safe and no_sep

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_config_field_exists():
    """测试退役配置 - 字段存在且为列表"""
    try:
        return isinstance(CoreConfig.retired_clients, list)

    except Exception:
        return False


async def _test_parse_basic_route():
    """测试关系解析 - 解析出源与目标，分隔符两侧的空白被去除"""
    try:
        routes = parse_retired_routes(["QQ -> QQBot", "  KOOK->Discord  "])
        return routes == {"QQ": "QQBot", "KOOK": "Discord"}

    except Exception:
        return False


async def _test_parse_source_only():
    """测试关系解析 - 只写源时目标为 None，表示不提供迁移去处"""
    try:
        return parse_retired_routes(["QQ"]) == {"QQ": None}

    except Exception:
        return False


async def _test_parse_ignores_malformed():
    """测试关系解析 - 含多个分隔符或源为空的项被整条忽略"""
    try:
        routes = parse_retired_routes(["QQ -> QQBot -> Discord", "-> Discord", "", "KOOK -> Discord"])
        return routes == {"KOOK": "Discord"}

    except Exception:
        return False


async def _test_parse_duplicate_source_keeps_first():
    """测试关系解析 - 同一源重复出现时以首次为准"""
    try:
        return parse_retired_routes(["QQ -> QQBot", "QQ -> Discord"]) == {"QQ": "QQBot"}

    except Exception:
        return False


async def _test_route_allows_matching_pair():
    """测试来源校验 - 同一条关系的两端放行"""
    try:
        original = CoreConfig.retired_clients
        CoreConfig.retired_clients = ["QQ -> QQBot", "KOOK -> Discord"]
        reload_retired_routes()
        result = is_merge_route_allowed("QQ", "QQBot")
        CoreConfig.retired_clients = original
        reload_retired_routes()
        return result

    except Exception:
        return False


async def _test_route_rejects_cross_pair():
    """测试来源校验 - 跨关系兑换被拒绝"""
    try:
        original = CoreConfig.retired_clients
        CoreConfig.retired_clients = ["QQ -> QQBot", "KOOK -> Discord"]
        reload_retired_routes()
        cross = is_merge_route_allowed("QQ", "Discord")
        unknown = is_merge_route_allowed("Telegram", "QQBot")
        none_safe = is_merge_route_allowed(None, "QQBot")
        CoreConfig.retired_clients = original
        reload_retired_routes()
        return not cross and not unknown and not none_safe

    except Exception:
        return False


async def _test_route_rejects_when_no_target():
    """测试来源校验 - 源未配置迁移去处时一律拒绝"""
    try:
        original = CoreConfig.retired_clients
        CoreConfig.retired_clients = ["QQ"]
        reload_retired_routes()
        result = is_merge_route_allowed("QQ", "QQBot")
        CoreConfig.retired_clients = original
        reload_retired_routes()
        return not result

    except Exception:
        return False


async def _test_merge_is_allowed():
    """测试退役白名单 - merge 模块获得放行"""
    try:
        return is_module_allowed_when_retired("merge") and "merge" in RETIRED_ALLOWED_MODULES

    except Exception:
        return False


async def _test_other_module_blocked():
    """测试退役白名单 - 其余模块一律拦下"""
    try:
        return not is_module_allowed_when_retired("wiki") and not is_module_allowed_when_retired(None)

    except Exception:
        return False


async def _test_push_filters_retired_target():
    """测试推送过滤 - 退役平台的会话被滤除，其余保留"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        kept = filter_retired_targets(
            [
                "RETIRETEST|Group|push1",
                "ALIVETEST|Group|push1",
                "RETIRETEST|Private|push2",
                "OTHER|Group|push3",
            ]
        )
        return kept == ["ALIVETEST|Group|push1", "OTHER|Group|push3"]

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_push_filter_keeps_all_when_unconfigured():
    """测试推送过滤 - 未配置迁移关系时不滤除任何会话"""
    original = CoreConfig.retired_clients
    try:
        _use_routes([])
        ids = ["QQ|Group|1", "QQBot|Group|2"]
        return filter_retired_targets(ids) == ids

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_retired_yields_to_alive():
    """测试通道让位 - 同通道存在非退役会话时退役会话让位"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y1": 1, "ALIVETEST|Group|y1": 1}
        return should_yield_channel("RETIRETEST|Group|y1", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_retired_alone_does_not_yield():
    """测试通道让位 - 通道内只剩退役会话时照常认领"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y2": 1}
        return not should_yield_channel("RETIRETEST|Group|y2", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_different_channel_does_not_yield():
    """测试通道让位 - 非退役会话位于其他通道时不让位"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y3": 1, "ALIVETEST|Group|y3": 2}
        return not should_yield_channel("RETIRETEST|Group|y3", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_alive_never_yields():
    """测试通道让位 - 非退役会话自身不适用让位规则"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y4": 1, "ALIVETEST|Group|y4": 1}
        return not should_yield_channel("ALIVETEST|Group|y4", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


@func_case
async def test_retired_gate(tester: Tester):
    """core.retired: 迁移关系、退役判定与介入点测试"""
    await tester.test(_test_config_field_exists, "配置字段存在测试")
    await tester.test(_test_parse_basic_route, "关系解析基本测试")
    await tester.test(_test_parse_source_only, "只写源测试")
    await tester.test(_test_parse_ignores_malformed, "格式错误忽略测试")
    await tester.test(_test_parse_duplicate_source_keeps_first, "重复源取首次测试")
    await tester.test(_test_client_judgement, "客户端判定测试")
    await tester.test(_test_target_judgement, "场景 ID 判定测试")
    await tester.test(_test_route_allows_matching_pair, "同关系放行测试")
    await tester.test(_test_route_rejects_cross_pair, "跨关系拒绝测试")
    await tester.test(_test_route_rejects_when_no_target, "无去处拒绝测试")
    await tester.test(_test_merge_is_allowed, "白名单放行测试")
    await tester.test(_test_other_module_blocked, "非白名单拦截测试")
    await tester.test(_test_push_filters_retired_target, "推送过滤测试")
    await tester.test(_test_push_filter_keeps_all_when_unconfigured, "未配置时不过滤测试")
    await tester.test(_test_retired_yields_to_alive, "退役让位测试")
    await tester.test(_test_retired_alone_does_not_yield, "独占通道不让位测试")
    await tester.test(_test_different_channel_does_not_yield, "跨通道不让位测试")
    await tester.test(_test_alive_never_yields, "非退役不让位测试")

    return tester
