"""core.retired 单元测试 - 迁移关系解析、退役判定与介入点。

本文件集中放置所有改动 ``CoreConfig.retired_clients`` 的用例：``tester.py`` 并发执行各个
func_case，而该配置与 ``RETIRED_ROUTES`` 是进程级全局状态，分散在多个文件中改动会互相覆盖。
同一 func_case 内部则是串行的，因此集中于此即可避免竞争。

末尾的等待任务用例须要数据库与已加载的模块，因为它们经由真实的 ``parser()`` 求证介入点的位置，
而非只验判据本身。
"""

import asyncio
from unittest.mock import patch

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain
from core.builtins.parser.message import parser
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.session.tasks import SessionTaskManager
from core.config.base import CoreConfig
from core.database.models import TargetUnionBind, TargetUnionInfo
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
    """测试推送过滤 - 退役平台的场景被滤除，其余保留"""
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
    """测试推送过滤 - 未配置迁移关系时不滤除任何场景"""
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
    """测试通道让位 - 同通道存在非退役场景时退役场景让位"""
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
    """测试通道让位 - 通道内只剩退役场景时照常认领"""
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
    """测试通道让位 - 非退役场景位于其他通道时不让位"""
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
    """测试通道让位 - 非退役场景自身不适用让位规则"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y4": 1, "ALIVETEST|Group|y4": 1}
        return not should_yield_channel("ALIVETEST|Group|y4", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _session(target_id: str, client: str) -> MessageSession:
    """建一个消息内容为空的会话，用于只跑到 parser 的任务检查一段。"""
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client}|Group",
        client_name=client,
        sender_id=f"{client}|1",
        messages=MessageChain.assign(Plain("")),
        create=True,
    )
    return MessageSession(session_info=session_info)


async def _probe_wait_task(prefix: str, with_alive: bool) -> bool:
    """
    令退役场景的一条消息走一遍真实的 ``parser()``，观察同通道内挂起的等待任务是否被它触发。

    等待任务按消息通道共享，故须由 ``parser()`` 而非判据函数本身求证：判据即便正确，
    介入点排在任务检查之后仍拦不下这条路径。空消息在任务检查之后随即返回，恰好只跑到待测的这一段。

    :param prefix: 客户端名前缀，各用例互不相同以免共用 union。
    :param with_alive: 通道内是否另有存活场景。
    :return: 等待任务是否被退役场景的消息触发。
    """
    retired_client = f"{prefix}R"
    retired_target = f"{retired_client}|Group|x"
    _use_routes([f"{retired_client} -> {prefix}A"])

    union = await TargetUnionInfo.resolve_union(retired_target)
    holder_target = retired_target
    if with_alive:
        # 并入同一通道号，两个平台场景自此指向同一个现实场景，等待任务随之共享
        holder_target = f"{prefix}A|Group|y"
        await union.bind_id(holder_target)
        await TargetUnionBind.filter(target_id=holder_target).update(channel_id=1)

    holder = await _session(holder_target, f"{prefix}A" if with_alive else retired_client)
    retired = await _session(retired_target, retired_client)

    SessionTaskManager._task_list.clear()
    try:
        # all_ 的任务只按消息通道建键，最能直击同一频道键内的抢占
        SessionTaskManager.add_task(holder, asyncio.Event(), all_=True, timeout=60)
        await parser(retired)
        return SessionTaskManager.get()[holder.session_info.channel_key]["all"][holder]["active"] is False

    finally:
        SessionTaskManager._task_list.clear()


async def _test_retired_yields_wait_task():
    """测试等待任务 - 同通道存在存活场景时，退役场景的消息不触发挂起的等待任务"""
    original = CoreConfig.retired_clients
    try:
        return not await _probe_wait_task("WTA", with_alive=True)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_retired_keeps_wait_task_when_alone():
    """测试等待任务 - 通道内只剩退役场景时照常触发，迁移流程的确认不致中断"""
    original = CoreConfig.retired_clients
    try:
        return await _probe_wait_task("WTB", with_alive=False)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_union_push_skips_retired():
    """测试组内推送 - 退役平台的场景不参与组内推送，队首落到存活场景"""
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RPUSHR -> RPUSHA"])
        union = await TargetUnionInfo.resolve_union("RPUSHR|Group|p")
        await union.bind_id("RPUSHA|Group|p")
        # 并入同一通道：退役场景若不被滤除，便会以组内首位的身份抢到队首
        await TargetUnionBind.filter(target_id__in=["RPUSHR|Group|p", "RPUSHA|Group|p"]).update(channel_id=1)

        sent = []

        async def _record(target, message, **kwargs):
            sent.append(target.target_id)

        alive = {c: {"target_prefix_list": [c]} for c in ("RPUSHR", "RPUSHA")}
        with (
            patch.object(Alive, "get_alive", return_value=alive),
            patch.object(Bot, "send_direct_message", _record),
        ):
            await Bot.send_direct_message_to_union_target(union.union_id, Plain("x"))
        return sent == ["RPUSHA|Group|p"]

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
    await tester.test(_test_retired_yields_wait_task, "退役让出等待任务测试")
    await tester.test(_test_retired_keeps_wait_task_when_alone, "独占通道保留等待任务测试")
    await tester.test(_test_union_push_skips_retired, "组内推送滤除退役测试")

    return tester
