"""modules.core.bind 单元测试 - bind auto 握手的并发收敛（需要数据库）。"""

import asyncio
import re

from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.constants.exceptions import SessionFinished
from core.database.models import TargetInfo, TargetUnionBind
from core.tester import func_case, Tester
from core.tester.mock.parser import parser
from core.tester.mock.session import MockMessageSession
from modules.core.bind import _complete_channel_handshake

PROBE_PATTERN = re.compile(r"bind channel (probe|confirm) (\S+)")


async def _session(target_id: str, text: str = "", sender: str = "admin") -> MockMessageSession:
    """
    构造一条指定会话的消息，模拟同一个现实会话中来自不同平台的机器人。

    :param sender: 消息的发送者。握手口令由对方机器人发出，而非管理员发出，
                   而机器人账号仅在接收方所在平台的命名空间内有意义，故前缀取接收方的。
    """
    msg = MockMessageSession(text, is_ci=True)
    await msg.async_init(text)
    client = target_id.split("|")[0]
    msg.session_info = await SessionInfo.assign(
        target_id=target_id,
        client_name=client,
        target_from="|".join(target_id.split("|")[:2]),
        sender_id=f"{client}|{sender}",
        sender_from=client,
        messages=MessageChain.assign(text),
    )
    msg.session_info.superuser = True

    async def _yes(message_chain=None, **kwargs):
        # 实际的确认需等待用户回复，中间必然让出控制权；此处同样让出一次，以便并发用例能够真正交错。
        await asyncio.sleep(0)
        return True

    msg.wait_confirm = _yes
    msg.check_permission = _yes
    return msg


async def _run(target_id: str, text: str, sender: str = "admin") -> list[str]:
    """
    以指定会话执行一条命令，返回该会话产生的输出行。
    """
    msg = await _session(target_id, text, sender)
    try:
        await parser(msg)
    except SessionFinished:
        pass
    return msg.action


def _tokens(lines: list[str], kind: str) -> list[str]:
    """
    从输出中提取握手口令。
    """
    found = []
    for line in lines:
        match = PROBE_PATTERN.search(str(line))
        if match and match.group(1) == kind:
            found.append(match.group(2))
    return found


async def _handshake(prefix: str) -> tuple[str, str]:
    """
    完整执行一遍两个机器人同时响应 ``~bind auto`` 的过程，返回双方的 target_id。

    实际情形即是如此：绑定尚未建立，通道去重与互认记录均未生效，
    同一会话内的每个机器人都会将该命令视作发给自己的，于是各自发起一轮握手。
    """
    a, b = f"{prefix}A|Group|1", f"{prefix}B|Group|1"

    token_a = _tokens(await _run(a, "~bind auto"), "probe")[0]
    token_b = _tokens(await _run(b, "~bind auto"), "probe")[0]

    # 两轮 probe 交叉送达；让位机制应使其中一轮退出，仅剩一轮进入 confirm。
    confirms = [(b, t) for t in _tokens(await _run(b, f"~bind channel probe {token_a}", sender="peer_bot"), "confirm")]
    confirms += [(a, t) for t in _tokens(await _run(a, f"~bind channel probe {token_b}", sender="peer_bot"), "confirm")]

    for responder, confirm_token in confirms:
        # confirm 由发起方一侧接收，另一侧即为其发出方。
        initiator = a if responder == b else b
        await _run(initiator, f"~bind channel confirm {confirm_token}", sender="peer_bot")
    return a, b


async def _orphan_unions() -> int:
    """
    统计没有任何会话指向的场景组。重复合并会遗留此类孤儿组，写入其中的数据将无法被读取。
    """
    bound = set(await TargetUnionBind.all().values_list("union_id", flat=True))
    return sum(1 for union_id in await TargetInfo.all().values_list("union_id", flat=True) if union_id not in bound)


async def _test_only_one_round_survives():
    """测试 bind auto - 两轮握手交叉时仅有一轮进入 confirm"""
    try:
        a, b = "ONEROUND1|Group|1", "ONEROUND2|Group|1"
        token_a = _tokens(await _run(a, "~bind auto"), "probe")[0]
        token_b = _tokens(await _run(b, "~bind auto"), "probe")[0]

        # 若不让位，双方都会应答对方，产生两个 confirm，同一对会话将被合并两次。
        confirms = _tokens(await _run(b, f"~bind channel probe {token_a}", sender="peer_bot"), "confirm")
        confirms += _tokens(await _run(a, f"~bind channel probe {token_b}", sender="peer_bot"), "confirm")
        return len(confirms) == 1

    except Exception:
        return False


async def _test_concurrent_completion_merges_once():
    """测试 bind auto - 两轮握手同时闭合时仅合并一次"""
    try:
        a, b = "RACE1|Group|1", "RACE2|Group|1"
        await TargetInfo.resolve_union(a)
        await TargetInfo.resolve_union(b)
        before = await _orphan_unions()

        # 绕过让位机制直接构造两轮，模拟让位未生效（如某一平台的 probe 投递延迟）的最坏情况。
        rounds = []
        for initiator_id, responder_id in ((a, b), (b, a)):
            rounds.append(
                {
                    "initiator": await _session(initiator_id),
                    "responder": await _session(responder_id),
                    "initiator_bot_id": f"{responder_id.split('|')[0]}|peer_bot",
                    "responder_bot_id": f"{initiator_id.split('|')[0]}|peer_bot",
                }
            )
        await asyncio.gather(*(_complete_channel_handshake(entry) for entry in rounds))

        target_a = await TargetInfo.resolve_union(a)
        target_b = await TargetInfo.resolve_union(b)
        if target_a.union_id != target_b.union_id:
            return False
        # 若各建一个新组，后建的那个组不会有任何会话指向它。
        if await _orphan_unions() != before:
            return False
        # 互认记录须写入实际生效的那个组，写入孤儿组等同于未写入。
        return sorted(target_a.list_peer_bots(a) + target_a.list_peer_bots(b)) == ["RACE1|peer_bot", "RACE2|peer_bot"]

    except Exception:
        return False


async def _test_concurrent_auto_records_bots_id():
    """测试 bind auto - 机器人账号记录在实际生效的组上"""
    try:
        a, b = await _handshake("BOTSID")

        # 重复合并会将互认记录写入没有任何会话指向的孤儿组，等同于未写入。
        # 双方各记录一条对方的账号，按各自平台的命名空间存放。
        target = await TargetInfo.resolve_union(a)
        bots_id = target.list_peer_bots(a) + target.list_peer_bots(b)
        return sorted(bots_id) == ["BOTSIDA|peer_bot", "BOTSIDB|peer_bot"]

    except Exception:
        return False


async def _test_unbind_forgets_peer_bots():
    """测试 bind auto - 解绑后互认记录被清除，可重新建立关联"""
    try:
        a, b = await _handshake("FORGET")
        target = await TargetInfo.resolve_union(a)
        if not target.list_peer_bots(a):
            return False

        await target.unbind_id(b)

        # parser 即依据这份名单屏蔽对端机器人。保留的一侧若仍记录着对方，
        # 重新配对所用的 probe / confirm 会被直接丢弃，握手无法闭合，双方也就无法重新建立关联。
        stayed = await TargetInfo.resolve_union(a)
        left = await TargetInfo.resolve_union(b)
        return not stayed.list_peer_bots(a) and not left.list_peer_bots(b)

    except Exception:
        return False


async def _test_rebind_after_unbind():
    """测试 bind auto - 解绑后重新执行握手仍能成立

    仅覆盖流程本身。「因屏蔽而无法重新绑定」实际发生在 core/builtins/parser/message.py，
    而测试使用的是不执行该屏蔽的 mock parser，该判定条件由上面的清除用例覆盖。
    """
    try:
        a, b = await _handshake("REBIND")
        target = await TargetInfo.resolve_union(a)
        await target.unbind_id(b)

        await _handshake("REBIND")

        rebound_a = await TargetInfo.resolve_union(a)
        rebound_b = await TargetInfo.resolve_union(b)
        if rebound_a.union_id != rebound_b.union_id:
            return False
        return sorted(rebound_a.list_peer_bots(a) + rebound_a.list_peer_bots(b)) == [
            "REBINDA|peer_bot",
            "REBINDB|peer_bot",
        ]

    except Exception:
        return False


async def _test_peer_bots_scoped_per_target():
    """测试 bind auto - 互认记录按观察方分开存放，各自只读取本方的记录"""
    try:
        a, b = await _handshake("SCOPE")
        target = await TargetInfo.resolve_union(a)

        # 账号按观察方所在平台的命名空间记录，若混在一个扁平列表中将无法区分归属。
        return target.list_peer_bots(a) == ["SCOPEA|peer_bot"] and target.list_peer_bots(b) == ["SCOPEB|peer_bot"]

    except Exception:
        return False


async def _test_second_handshake_is_noop():
    """测试 bind auto - 已处于同组同通道时重复执行不会再次合并"""
    try:
        a, b = await _handshake("REPEAT")
        before = await TargetInfo.resolve_union(a)

        await _handshake("REPEAT")

        after = await TargetInfo.resolve_union(a)
        if after.union_id != before.union_id:
            return False
        return (await TargetInfo.resolve_union(b)).union_id == after.union_id

    except Exception:
        return False


@func_case
async def test_bind_auto(tester: Tester):
    """modules.core.bind: bind auto 握手测试"""
    await tester.test(_test_only_one_round_survives, "握手让位测试")
    await tester.test(_test_concurrent_completion_merges_once, "并发闭合只合并一次测试")
    await tester.test(_test_concurrent_auto_records_bots_id, "机器人账号落库测试")
    await tester.test(_test_peer_bots_scoped_per_target, "互认记录按会话分开测试")
    await tester.test(_test_unbind_forgets_peer_bots, "解绑摘除互认记录测试")
    await tester.test(_test_rebind_after_unbind, "解绑后重新绑定测试")
    await tester.test(_test_second_handshake_is_noop, "重复握手空转测试")

    return tester
