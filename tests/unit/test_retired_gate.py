"""core.utils.retired 单元测试 - 迁移关系解析、退役判定与介入点。"""

import asyncio
from unittest.mock import AsyncMock, patch

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
from core.loader import ModulesManager
from core.queue.contracts import PlatformAPI
from core.utils.retired import (
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
from modules.core.common_tools.bind import b as bind_module
from modules.core.hooks.routing import channel_claim_cache


def _use_routes(entries: list):
    original = CoreConfig.retired_clients
    CoreConfig.retired_clients = entries
    reload_retired_routes()
    return original


def _restore_routes(original: list):
    CoreConfig.retired_clients = original
    reload_retired_routes()


async def _test_client_judgement():
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


async def _test_parse_basic_route():
    try:
        routes = parse_retired_routes(["QQ -> QQBot", "  KOOK->Discord  "])
        return routes == {"QQ": "QQBot", "KOOK": "Discord"}

    except Exception:
        return False


async def _test_parse_source_only():
    try:
        return parse_retired_routes(["QQ"]) == {"QQ": None}

    except Exception:
        return False


async def _test_parse_ignores_malformed():
    try:
        routes = parse_retired_routes(["QQ -> QQBot -> Discord", "-> Discord", "", "KOOK -> Discord"])
        return routes == {"KOOK": "Discord"}

    except Exception:
        return False


async def _test_parse_duplicate_source_keeps_first():
    try:
        return parse_retired_routes(["QQ -> QQBot", "QQ -> Discord"]) == {"QQ": "QQBot"}

    except Exception:
        return False


async def _test_route_allows_matching_pair():
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
    try:
        return is_module_allowed_when_retired("merge") and "merge" in RETIRED_ALLOWED_MODULES

    except Exception:
        return False


async def _test_other_module_blocked():
    try:
        return not is_module_allowed_when_retired("wiki") and not is_module_allowed_when_retired(None)

    except Exception:
        return False


async def _test_push_filters_retired_target():
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
    original = CoreConfig.retired_clients
    try:
        _use_routes(["RETIRETEST -> ALIVETEST"])
        channels = {"RETIRETEST|Group|y4": 1, "ALIVETEST|Group|y4": 1}
        return not should_yield_channel("ALIVETEST|Group|y4", channels, 1)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _session(target_id: str, client: str, text: str = "") -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client}|Group",
        client_name=client,
        sender_id=f"{client}|1",
        messages=MessageChain.assign(Plain(text)),
        create=True,
    )
    return MessageSession(session_info=session_info)


async def _probe_wait_task(prefix: str, with_alive: bool) -> bool:
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
        # all_ 任务按物理场景建稳定 bucket，check() 再按当前消息通道展开。
        flag = asyncio.Event()
        SessionTaskManager.add_task(holder, flag, all_=True, timeout=60)
        # 这里只模拟平台成功持有上下文，parser 与等待任务路由仍执行真实逻辑。
        hold = AsyncMock(return_value=None)
        with patch.object(PlatformAPI, "hold_context", new=hold):
            await parser(retired)
        task = SessionTaskManager.get()[holder.session_info.target_id]["all"][holder]
        if with_alive:
            hold.assert_not_awaited()
        else:
            hold.assert_awaited_once_with(retired.session_info)
        return task["active"] is False and flag.is_set() and task["result"] is retired

    finally:
        SessionTaskManager._task_list.clear()


async def _test_retired_yields_wait_task():
    original = CoreConfig.retired_clients
    try:
        return not await _probe_wait_task("WTA", with_alive=True)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _test_retired_keeps_wait_task_when_alone():
    original = CoreConfig.retired_clients
    try:
        return await _probe_wait_task("WTB", with_alive=False)

    except Exception:
        return False

    finally:
        _restore_routes(original)


async def _probe_merge_command_route(command: str, order: tuple[str, str], prefix: str) -> bool:
    retired_client = f"{prefix}R"
    alive_client = f"{prefix}A"
    retired_target = f"{retired_client}|Group|x"
    alive_target = f"{alive_client}|Group|y"
    _use_routes([f"{retired_client} -> {alive_client}"])

    union = await TargetUnionInfo.resolve_union(retired_target)
    await union.bind_id(alive_target)
    await TargetUnionBind.filter(target_id__in=[retired_target, alive_target]).update(channel_id=1)

    sessions = {
        "retired": await _session(retired_target, retired_client, command),
        "alive": await _session(alive_target, alive_client, command),
    }
    executed: list[str] = []

    async def _record(msg, modules, command_first_word, identify_str):
        executed.append(msg.session_info.client_name)

    module = ModulesManager.modules[bind_module.module_name]
    previous_load = module._db_load
    module._db_load = True
    channel_claim_cache.clear()
    try:
        with (
            patch.object(ModulesManager, "return_modules_list", return_value={"bind": module}),
            patch("core.builtins.parser.message._execute_module", new=_record),
        ):
            for side in order:
                await parser(sessions[side])
        expected = retired_client if command == "~merge" else alive_client
        return executed == [expected]
    finally:
        channel_claim_cache.clear()
        module._db_load = previous_load


async def _test_merge_start_routes_to_retired_source():
    original = CoreConfig.retired_clients
    try:
        return await _probe_merge_command_route("~merge", ("alive", "retired"), "MRS")
    finally:
        _restore_routes(original)


async def _test_merge_token_routes_to_alive_target():
    original = CoreConfig.retired_clients
    try:
        return await _probe_merge_command_route("~merge token ABCDEF", ("retired", "alive"), "MRT")
    finally:
        _restore_routes(original)


async def _test_union_push_skips_retired():
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
    """core.utils.retired: 迁移关系、退役判定与介入点测试"""
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
    await tester.test(_test_merge_start_routes_to_retired_source, "迁移发起命令路由测试")
    await tester.test(_test_merge_token_routes_to_alive_target, "迁移兑换命令路由测试")
    await tester.test(_test_union_push_skips_retired, "组内推送滤除退役测试")

    return tester
