"""QQBot 群聊「正在输入中」提示的撤回时机测试。

QQ 群没有原生输入状态能力，适配器以「先发一条提示消息、事后撤回」的方式模拟。
提示消息一旦漏撤就会永久留在群里，且用户无从自行清理，因此其撤回必须对每条
异常路径都成立——包括上下文已销毁、同一会话重复开启输入状态等情形。
"""

import asyncio

from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_group_prefix
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 压缩生产默认的等待秒数，使各用例得以在毫秒级跑完
TEST_DELAY = 0.05


def _make_session(session_id: str) -> SessionInfo:
    """构造一个群聊会话，只填充输入状态机用到的字段。

    :param session_id: 会话 ID，各用例之间须互不相同。
    :return: 可交由 start_typing 使用的会话信息。
    """
    return SessionInfo(
        target_id=f"{target_group_prefix}|test_group",
        sender_id="QQ|Tiny|1",
        target_from=target_group_prefix,
        client_name="QQBot",
        session_id=session_id,
    )


class _Recorder:
    """接管收发接口，记录调用而不触网。

    区分「输入提示」与「机器人自身消息」两类发送，便于断言前者是否被撤回。
    """

    def __init__(self):
        self.prompts: list[str] = []
        self.messages: list[str] = []
        self.deleted: list[str] = []
        self._counter = 0

    def __enter__(self):
        cm = QQBotContextManager
        # 取类字典中的原始描述符，避免恢复时把 classmethod 降级成普通属性
        self._orig_send = cm.__dict__.get("send_message")
        self._orig_delete = cm.__dict__.get("delete_message")
        self._orig_delay = cm.TYPING_PROMPT_DELAY

        async def fake_send(session_info, message, *args, **kwargs):
            self._counter += 1
            msg_id = f"msg-{self._counter}"
            if kwargs.get("_typing_prompt"):
                self.prompts.append(msg_id)
            else:
                self.messages.append(msg_id)
                # 复刻生产 send_message 开头对「机器人已发言」的登记
                cm._on_message_sent(session_info)
            return [msg_id]

        async def fake_delete(session_info, message_id, reason=None):
            self.deleted.extend([message_id] if isinstance(message_id, str) else list(message_id))

        cm.send_message = staticmethod(fake_send)
        cm.delete_message = staticmethod(fake_delete)
        cm.TYPING_PROMPT_DELAY = TEST_DELAY
        return self

    def __exit__(self, *exc_info):
        cm = QQBotContextManager
        cm.send_message = self._orig_send
        cm.delete_message = self._orig_delete
        cm.TYPING_PROMPT_DELAY = self._orig_delay
        return False

    @property
    def leaked(self) -> list[str]:
        """已发出但未被撤回的输入提示。"""
        return [p for p in self.prompts if p not in self.deleted]


class _Session:
    """在受控的上下文中跑一个会话，退出时清干净全局状态。"""

    def __init__(self, session_id: str):
        self.session = _make_session(session_id)

    async def __aenter__(self) -> SessionInfo:
        QQBotContextManager.context[self.session.session_id] = object()
        return self.session

    async def __aexit__(self, *exc_info):
        await QQBotContextManager.end_typing(self.session)
        QQBotContextManager.context.pop(self.session.session_id, None)
        return False


async def _wait_prompt_sent(rec: _Recorder) -> bool:
    """等到输入提示发出为止。

    :return: 提示是否已发出。
    """
    for _ in range(40):
        await asyncio.sleep(TEST_DELAY / 2)
        if rec.prompts:
            return True
    return False


async def _test_prompt_recalled_after_bot_message() -> bool:
    """机器人发出自身消息后，输入提示应随即撤回，无须等到输入状态结束"""
    with _Recorder() as rec:
        async with _Session("typing-after-message") as session:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Typing prompt was not sent after the delay window")
                return False

            await QQBotContextManager.send_message(session, None)
            await asyncio.sleep(TEST_DELAY * 3)

            if rec.leaked:
                Logger.error(f"Typing prompt left behind after the bot sent its own message: {rec.leaked}")
                return False
            return True


async def _test_prompt_recalled_when_context_dropped() -> bool:
    """上下文已销毁时结束输入状态，不得抛错，且仍须撤回输入提示"""
    with _Recorder() as rec:
        session = _make_session("typing-context-dropped")
        QQBotContextManager.context[session.session_id] = object()
        try:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Typing prompt was not sent after the delay window")
                return False

            # 模拟 release_context / del_context 先一步执行
            QQBotContextManager.context.pop(session.session_id, None)
            try:
                await QQBotContextManager.end_typing(session)
            except Exception:
                Logger.exception("end_typing raised after the context had been dropped")
                return False
            await asyncio.sleep(TEST_DELAY * 3)

            if rec.leaked:
                Logger.error(f"Typing prompt left behind after the context was dropped: {rec.leaked}")
                return False
            return True
        finally:
            QQBotContextManager.context.pop(session.session_id, None)


async def _test_prompt_recalled_on_repeated_start() -> bool:
    """同一会话重复开启输入状态时，先前的输入提示不得被遗弃"""
    with _Recorder() as rec:
        async with _Session("typing-repeated-start") as session:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Typing prompt was not sent after the delay window")
                return False
            first_prompt = rec.prompts[0]

            # 后一轮尚在进行，其自身的提示还未到撤回时机，故只针对前一轮断言
            await QQBotContextManager.start_typing(session)
            await asyncio.sleep(TEST_DELAY * 3)

            if first_prompt not in rec.deleted:
                Logger.error(f"Typing prompt {first_prompt} left behind after typing restarted")
                return False
            return True


async def _test_no_prompt_when_message_sent_early() -> bool:
    """机器人在等待窗口内已发言时，不应再补发输入提示"""
    with _Recorder() as rec:
        async with _Session("typing-early-message") as session:
            await QQBotContextManager.start_typing(session)
            await QQBotContextManager.send_message(session, None)
            await asyncio.sleep(TEST_DELAY * 4)

            if rec.prompts:
                Logger.error(f"Typing prompt sent even though the bot had already spoken: {rec.prompts}")
                return False
            return True


async def _test_prompt_recalled_on_end_typing() -> bool:
    """常规路径：输入状态结束时须撤回输入提示"""
    with _Recorder() as rec:
        session = _make_session("typing-end-normally")
        QQBotContextManager.context[session.session_id] = object()
        try:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Typing prompt was not sent after the delay window")
                return False

            await QQBotContextManager.end_typing(session)
            await asyncio.sleep(TEST_DELAY * 3)

            if rec.leaked:
                Logger.error(f"Typing prompt left behind after typing ended: {rec.leaked}")
                return False
            return True
        finally:
            QQBotContextManager.context.pop(session.session_id, None)


@func_case
async def test_qqbot_typing(tester: Tester):
    """bots.qqbot.context: 群聊输入提示的撤回时机测试"""
    await tester.test(_test_prompt_recalled_after_bot_message, "机器人发言后撤回输入提示测试")
    await tester.test(_test_prompt_recalled_when_context_dropped, "上下文销毁后撤回输入提示测试")
    await tester.test(_test_prompt_recalled_on_repeated_start, "重复开启输入状态撤回测试")
    await tester.test(_test_no_prompt_when_message_sent_early, "窗口内已发言不补发提示测试")
    await tester.test(_test_prompt_recalled_on_end_typing, "输入状态结束撤回提示测试")

    return tester
