"""Bot.send_direct_message_to_union_target 单元测试 - 按消息通道去重的组内推送。

退役场景的滤除一并由本方法承担，但那条用例改动 ``CoreConfig.retired_clients``，
按既有约定归入 ``test_retired_gate.py``。
"""

from unittest.mock import patch

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.message.internal import Plain
from core.database.models import TargetUnionBind, TargetUnionInfo
from core.tester import func_case, Tester

# 各用例使用的客户端名。保活表由测试自行提供，故不必是真实存在的平台。
_CLIENTS = ("UPUSHA", "UPUSHB", "UPUSHC")

# 保活表的最简形态：键为客户端名，前缀用于由场景 ID 反查客户端。
_ALIVE = {c: {"target_prefix_list": [c]} for c in _CLIENTS}


async def _push(union_id: str, message, alive: dict | None = None) -> list[tuple]:
    """
    在受控的在线状态下跑一次组内推送。

    :param union_id: 目标场景组的 union ID。
    :param message: 消息内容或消息工厂。
    :param alive: 保活表，缺省为全部客户端在线。
    :return: ``(会话, 消息)`` 形式的发送记录。
    """
    calls = []

    async def _record(target, msg, **kwargs):
        calls.append((target, msg))

    with (
        patch.object(Alive, "get_alive", return_value=alive if alive is not None else _ALIVE),
        patch.object(Bot, "send_direct_message", _record),
    ):
        await Bot.send_direct_message_to_union_target(union_id, message)
    return calls


async def _bind(prefix: str, *targets: tuple[str, int]) -> str:
    """
    建一个场景组并按给定的通道号绑定若干平台场景。

    :param prefix: 场景 ID 的尾段前缀，各用例互不相同以免共用 union。
    :param targets: ``(客户端名, 通道号)`` 序列，首项为组内的第一个场景。
    :return: 该组的 union ID。
    """
    head_client, head_channel = targets[0]
    union = await TargetUnionInfo.resolve_union(f"{head_client}|Group|{prefix}")
    for client, _ in targets[1:]:
        await union.bind_id(f"{client}|Group|{prefix}")
    for client, channel in targets:
        await TargetUnionBind.filter(target_id=f"{client}|Group|{prefix}").update(channel_id=channel)
    return union.union_id


async def _test_dedups_within_channel():
    """测试组内推送 - 同一消息通道内的多个会话仅推送一次"""
    try:
        union_id = await _bind("dedup", ("UPUSHA", 1), ("UPUSHB", 1))
        calls = await _push(union_id, Plain("x"))
        if len(calls) != 1:
            return False
        # 队首承担推送，同通道的其余会话降为发送失败时的下一跳
        session = calls[0][0]
        return session.target_id == "UPUSHA|Group|dedup" and session.next_hops == ["UPUSHB|Group|dedup"]

    except Exception:
        return False


async def _test_covers_every_channel():
    """测试组内推送 - 通道号不同的会话各自推送一次"""
    try:
        union_id = await _bind("split", ("UPUSHA", 1), ("UPUSHB", 2))
        calls = await _push(union_id, Plain("x"))
        return sorted(c[0].target_id for c in calls) == ["UPUSHA|Group|split", "UPUSHB|Group|split"]

    except Exception:
        return False


async def _test_skips_offline_channel():
    """测试组内推送 - 通道内客户端全部掉线时跳过，不落到已掉线的会话上"""
    try:
        union_id = await _bind("offline", ("UPUSHA", 1), ("UPUSHB", 2))
        # 仅 UPUSHB 在线，UPUSHA 所在通道无人可送
        alive = {"UPUSHB": {"target_prefix_list": ["UPUSHB"]}}
        calls = await _push(union_id, Plain("x"), alive=alive)
        return len(calls) == 1 and calls[0][0].target_id == "UPUSHB|Group|offline"

    except Exception:
        return False


async def _test_message_factory_receives_session():
    """测试组内推送 - 消息工厂按通道各调用一次，取到的是该通道的队首会话"""
    try:
        union_id = await _bind("factory", ("UPUSHA", 1), ("UPUSHB", 1), ("UPUSHC", 2))
        seen = []

        async def _build(session):
            seen.append(session.target_id)
            return Plain(session.target_id)

        calls = await _push(union_id, _build)
        # 两个通道各算一次消息，且工厂拿到的会话即实际承担推送的那个
        return (
            sorted(seen) == ["UPUSHA|Group|factory", "UPUSHC|Group|factory"]
            and len(calls) == 2
            and all(str(msg) == str(Plain(session.target_id)) for session, msg in calls)
        )

    except Exception:
        return False


async def _test_message_factory_may_skip():
    """测试组内推送 - 消息工厂返回 None 时不发送，供工厂按需自行处理"""
    try:
        union_id = await _bind("skip", ("UPUSHA", 1), ("UPUSHB", 2))
        seen = []

        async def _build(session):
            seen.append(session.target_id)
            # 仅其中一条通道有内容可发
            return Plain("x") if session.target_id.startswith("UPUSHA") else None

        calls = await _push(union_id, _build)
        return len(seen) == 2 and len(calls) == 1 and calls[0][0].target_id == "UPUSHA|Group|skip"

    except Exception:
        return False


async def _test_report_targets_dedup():
    """测试报错回传 - 同一现实场景即便配了多个上报场景也只收到一份"""
    try:
        await _bind("report", ("UPUSHA", 1), ("UPUSHB", 1))
        # 上报场景按平台场景 ID 配置，同一个现实场景的两个平台都被填了进来
        targets = ["UPUSHA|Group|report", "UPUSHB|Group|report"]
        sent = []

        async def _record(target, message, **kwargs):
            sent.append(target.target_id)

        with (
            patch("core.tos.report_targets", targets),
            patch.object(Alive, "get_alive", return_value=_ALIVE),
            patch.object(Bot, "send_direct_message", _record),
        ):
            from core.tos import tos_report

            await tos_report("UPUSHA|1", "UPUSHA|Group|report", "reason")
        return sent == ["UPUSHA|Group|report"]

    except Exception:
        return False


@func_case
async def test_union_push(tester: Tester):
    """core.builtins.bot: 按消息通道去重的组内推送测试"""
    await tester.test(_test_dedups_within_channel, "同通道去重测试")
    await tester.test(_test_covers_every_channel, "跨通道各推一次测试")
    await tester.test(_test_skips_offline_channel, "掉线通道跳过测试")
    await tester.test(_test_message_factory_receives_session, "消息工厂取到队首测试")
    await tester.test(_test_message_factory_may_skip, "消息工厂跳过发送测试")
    await tester.test(_test_report_targets_dedup, "报错回传去重测试")

    return tester
