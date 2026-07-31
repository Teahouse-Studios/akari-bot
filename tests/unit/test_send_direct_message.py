"""core.builtins.session.internal 单元测试 - send_direct_message 的消息归一化（需要数据库）。"""

from core.alive import Alive
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.database.models import JobQueuesTable
from core.tester import func_case, Tester


async def _session(client: str) -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id=f"{client}|Group|1",
        target_from=f"{client}|Group",
        client_name=client,
        sender_id=f"{client}|1",
        create=True,
    )
    return MessageSession(session_info=session_info)


async def _queued_message(client: str, message) -> dict:
    """
    以给定入参调用 send_direct_message，返回其入队任务里的 message 字段。
    """
    Alive.refresh_alive(client, target_prefix_list=[f"{client}|Group"], sender_prefix_list=[client])
    await JobQueuesTable.filter(action="send_message").delete()
    msg = await _session(client)
    await msg.send_direct_message(message)
    row = await JobQueuesTable.filter(action="send_message").first()
    return row.args["message"] if row else {}


async def _test_bare_element_is_wrapped():
    """测试直接发送 - bare 元素入队前须包成 MessageChain，否则队列反序列化会失败

    send_direct_message 曾把未归一化的原始入参直接入队。传入 bare 元素（如
    ``I18NContext(...)``）时，其序列化形态为 ``{"_type": "I18NContextElement", ...}``，
    缺少 values 字段，客户端按 MessageChain | MessageNodes 反序列化即抛 KeyError。
    """
    alive = Alive.values.copy()
    try:
        raw = await _queued_message("DIRECTA", I18NContext("message.success"))
        # 反序列化不抛异常，即证明入队的是完整 MessageChain 而非 bare 元素。
        back = converter.structure(raw, MessageChain | MessageNodes)
        return raw.get("_type") == "MessageChain" and isinstance(back, MessageChain)

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_plain_and_str_round_trip():
    """测试直接发送 - bare Plain 与纯字符串同样应能安全入队并还原"""
    alive = Alive.values.copy()
    try:
        for message in (Plain("hello"), "world"):
            raw = await _queued_message("DIRECTB", message)
            converter.structure(raw, MessageChain | MessageNodes)
            if raw.get("_type") != "MessageChain":
                return False
        return True

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


@func_case
async def test_send_direct_message(tester: Tester):
    """core.builtins.session.internal: send_direct_message 归一化测试"""
    await tester.test(_test_bare_element_is_wrapped, "bare 元素包装测试")
    await tester.test(_test_plain_and_str_round_trip, "Plain 与字符串往返测试")

    return tester
