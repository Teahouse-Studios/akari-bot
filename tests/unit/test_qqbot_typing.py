"""QQBot 群聊「正在输入中」提示的撤回时机测试。

QQ 群没有原生输入状态能力，适配器以「先发一条提示消息、事后撤回」的方式模拟。
提示消息一旦漏撤就会永久留在群里，且用户无从自行清理，因此其撤回必须对每条
异常路径都成立——包括上下文已销毁、同一会话重复开启输入状态等情形。

撤回由「机器人已发言」驱动，故该登记的落点亦在此一并把关：过早落下（如落在
图片转换之前或发送失败时）会使提示先行消失，空窗反而暴露。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from botpy.message import GroupMessage

from bots.qqbot.context import QQBotContextManager, TYPING_EMOTES, _TypingState
from bots.qqbot.info import target_c2c_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import I18NContextElement, ImageElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 压缩生产默认的等待秒数，使各用例得以在毫秒级跑完
TEST_DELAY = 0.05


class _FakeClient:
    """替身 botpy Client，覆盖适配器使用的高层发送接口。"""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.send_calls = 0
        self.image_kwargs = []
        self.typing_targets = []

    async def _send(self):
        self.send_calls += 1
        if self.send_calls <= self.fail_times:
            raise ValueError("send failed")
        return {"id": f"sent-{self.send_calls}"}

    async def send(self, target, **kwargs):
        return await self._send()

    async def send_image(self, target, **kwargs):
        self.image_kwargs.append(kwargs)
        return await self._send()

    async def send_typing(self, target, duration_seconds=60):
        self.typing_targets.append(target)
        return {"id": "typing-1"}


class _FakeGroupMessage(GroupMessage):
    """替身群消息，绕过 SDK 的构造流程，仅保留发送路径依赖的属性。"""

    def __init__(self, fail_times: int = 0):
        self.id = "source-message"
        self.group_openid = "fake_group"
        self.message_scene = None
        self.client = _FakeClient(fail_times)


class _ProbingImage(ImageElement):
    """转换耗时的图片，转换期间回调一次，用于观察当时的登记状态。"""

    # 不加类型注解，避免被 attrs 当作字段处理
    observer = None

    async def get(self) -> str:
        await asyncio.sleep(0.01)
        if _ProbingImage.observer:
            _ProbingImage.observer()
        return self.path


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
        self.prompt_messages: list[MessageChain] = []
        self.prompt_kwargs: list[dict] = []
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
                self.prompt_messages.append(message)
                self.prompt_kwargs.append(kwargs)
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


class _InFlightPromptRecorder:
    """模拟平台已接受 typing 消息、但 SDK 尚未返回消息 ID 的窗口。"""

    def __init__(self):
        self.prompt_started = asyncio.Event()
        self.release_prompt = asyncio.Event()
        self.prompts: list[str] = []
        self.deleted: list[str] = []
        self.platform_task: asyncio.Task[list[str]] | None = None

    def __enter__(self):
        cm = QQBotContextManager
        self._orig_send = cm.__dict__.get("send_message")
        self._orig_delete = cm.__dict__.get("delete_message")
        self._orig_delay = cm.TYPING_PROMPT_DELAY

        async def fake_send(session_info, message, *args, **kwargs):
            if not kwargs.get("_typing_prompt"):
                cm._on_message_sent(session_info)
                return ["response-message"]

            self.prompt_started.set()

            async def platform_send():
                await self.release_prompt.wait()
                self.prompts.append("late-typing-message")
                return ["late-typing-message"]

            self.platform_task = asyncio.create_task(platform_send())
            # botpy 的上层调用被取消时，底层 HTTP 请求仍可能已由平台受理并继续完成。
            # shield 在测试中复现这个「消息会发出，但调用方拿不到结果」的窗口。
            return await asyncio.shield(self.platform_task)

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
        return [prompt for prompt in self.prompts if prompt not in self.deleted]


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


async def _test_in_flight_prompt_recalled_after_response() -> bool:
    """响应先完成、typing 后落地时，仍须等待其消息 ID 并完成撤回。"""
    session = _make_session("typing-in-flight-after-response")
    QQBotContextManager.context[session.session_id] = object()
    with _InFlightPromptRecorder() as rec:
        end_task = None
        try:
            await QQBotContextManager.start_typing(session)
            await asyncio.wait_for(rec.prompt_started.wait(), timeout=TEST_DELAY * 10)

            # 正常回复先发送成功；随后 parser 会调用 end_typing。此时 typing 请求已经
            # 被平台受理，但 SDK 还没有返回其消息 ID。
            await QQBotContextManager.send_message(session, None)
            end_task = asyncio.create_task(QQBotContextManager.end_typing(session))
            await asyncio.sleep(TEST_DELAY)
            rec.release_prompt.set()
            await asyncio.wait_for(end_task, timeout=TEST_DELAY * 10)
            if rec.platform_task:
                await asyncio.wait_for(rec.platform_task, timeout=TEST_DELAY * 10)

            if rec.leaked:
                Logger.error(f"Typing prompt sent after the response was left behind: {rec.leaked}")
                return False
            if rec.prompts != ["late-typing-message"] or rec.deleted != ["late-typing-message"]:
                Logger.error(f"Unexpected in-flight prompt lifecycle: sent={rec.prompts}, deleted={rec.deleted}")
                return False
            return True
        finally:
            rec.release_prompt.set()
            if end_task and not end_task.done():
                await asyncio.gather(end_task, return_exceptions=True)
            await QQBotContextManager.end_typing(session)
            QQBotContextManager.context.pop(session.session_id, None)


async def _test_group_typing_uses_emote_when_enabled() -> bool:
    """开启 use_emote 后，群聊输入提示应附带随机 GIF，并强制走原生图片发送。"""
    if not TYPING_EMOTES:
        Logger.error("Typing emote assets are missing, the enabled-path test cannot run")
        return False

    with (
        patch("bots.qqbot.context.CoreConfig", new=SimpleNamespace(use_emote=True)),
        patch(
            "bots.qqbot.context.Random.choice",
            return_value=TYPING_EMOTES[0],
        ),
        _Recorder() as rec,
    ):
        async with _Session("typing-emote-enabled") as session:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Typing prompt with emote was not sent after the delay window")
                return False

            elements = rec.prompt_messages[0].values
            prompt = next((x for x in elements if isinstance(x, I18NContextElement)), None)
            image = next((x for x in elements if isinstance(x, ImageElement)), None)
            if prompt is None or prompt.key != "message.typing":
                Logger.error(f"Typing prompt text is missing or unexpected: {elements}")
                return False
            if image is None or image.path not in {str(path) for path in TYPING_EMOTES}:
                Logger.error(f"Typing prompt did not use an emote asset: {elements}")
                return False
            if rec.prompt_kwargs[0].get("_force_plain") is not True:
                Logger.error("Typing GIF must use QQBot's native image path to preserve animation")
                return False

    if rec.leaked:
        Logger.error(f"Typing prompt with emote was not recalled: {rec.leaked}")
        return False
    return True


async def _test_group_typing_omits_emote_when_disabled() -> bool:
    """关闭 use_emote 后，群聊输入提示应保持原有纯文本形态。"""
    with patch("bots.qqbot.context.CoreConfig", new=SimpleNamespace(use_emote=False)), _Recorder() as rec:
        async with _Session("typing-emote-disabled") as session:
            await QQBotContextManager.start_typing(session)
            if not await _wait_prompt_sent(rec):
                Logger.error("Plain typing prompt was not sent after the delay window")
                return False

            if rec.prompt_messages[0].contains(ImageElement):
                Logger.error(f"Typing prompt unexpectedly contains an emote: {rec.prompt_messages[0]}")
                return False
            if rec.prompt_kwargs[0].get("_force_plain") is not False:
                Logger.error("Plain typing prompt should retain the configured Markdown send path")
                return False

    if rec.leaked:
        Logger.error(f"Plain typing prompt was not recalled: {rec.leaked}")
        return False
    return True


async def _send_via_context(session: SessionInfo, ctx: _FakeGroupMessage, message) -> tuple[_TypingState, bool]:
    """在受控上下文中走一遍真实的发送流程。

    :param session: 目标会话。
    :param ctx: 替身群消息，充当平台上下文。
    :param message: 待发送的消息链。
    :return: 本轮的输入状态标志，以及发送是否成功。
    """
    sid = session.session_id
    state = _TypingState()
    QQBotContextManager.context[sid] = ctx
    QQBotContextManager.typing_states[sid] = state
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = ctx.client
    try:
        await QQBotContextManager.send_message(session, message, quote=False, _ignore_retries=True)
        return state, True
    except Exception:
        return state, False
    finally:
        QQBotContextManager.client = previous_client
        QQBotContextManager.context.pop(sid, None)
        QQBotContextManager.typing_states.pop(sid, None)


async def _test_c2c_uses_native_typing() -> bool:
    """C2C 会话应调用 botpy 的原生输入状态接口，并带上入站消息 ID。"""
    session = SessionInfo(
        target_id=f"{target_c2c_prefix}|friend",
        sender_id="QQBot|friend",
        target_from=target_c2c_prefix,
        client_name="QQBot",
        session_id="typing-c2c",
        message_id="source-message",
    )
    context = object()
    client = _FakeClient()
    state = _TypingState()
    state.finished.set()
    previous_client = QQBotContextManager.client
    QQBotContextManager.client = client
    QQBotContextManager.context[session.session_id] = context
    try:
        await QQBotContextManager._c2c_typing(session, state)
    finally:
        QQBotContextManager.client = previous_client
        QQBotContextManager.context.pop(session.session_id, None)
    if len(client.typing_targets) != 1:
        Logger.error(f"C2C typing should call botpy once, got {len(client.typing_targets)}")
        return False
    target = client.typing_targets[0]
    if target.scope != "c2c" or target.target_id != "friend" or target.message_id != "source-message":
        Logger.error(f"Unexpected C2C typing target: {target}")
        return False
    return True


async def _test_marked_after_send_succeeds() -> bool:
    """发送成功后须登记为已发言，否则输入提示将失去撤回时机"""
    session = _make_session("send-succeeds")
    ctx = _FakeGroupMessage()
    state, ok = await _send_via_context(session, ctx, MessageChain.assign(PlainElement.assign("hi")))

    if not ok:
        Logger.error("Sending should have succeeded in this case")
        return False
    if not state.spoken.is_set():
        Logger.error("A successfully sent message must be registered as the bot having spoken")
        return False
    return True


async def _test_not_marked_when_send_fails() -> bool:
    """发送失败时不得登记为已发言，否则提示会赶在消息真正发出之前被撤回"""
    session = _make_session("send-fails")
    ctx = _FakeGroupMessage(fail_times=1)
    state, ok = await _send_via_context(session, ctx, MessageChain.assign(PlainElement.assign("hi")))

    if ok:
        Logger.error("Sending should have failed in this case")
        return False
    if state.spoken.is_set():
        Logger.error("A failed send must not be registered as the bot having spoken")
        return False
    return True


async def _test_not_marked_while_converting_image() -> bool:
    """图片转换期间不得登记为已发言，转换可能远慢于发送本身"""
    session = _make_session("converting-image")
    ctx = _FakeGroupMessage()
    observed: list[bool] = []

    _ProbingImage.observer = lambda: observed.append(
        QQBotContextManager.typing_states[session.session_id].spoken.is_set()
    )
    try:
        state, ok = await _send_via_context(
            session, ctx, MessageChain.assign(_ProbingImage(path="fake.png", need_get=False))
        )
    finally:
        _ProbingImage.observer = None

    if not ok:
        Logger.error("Sending should have succeeded in this case")
        return False
    if not observed:
        Logger.error("The image was never converted, the test setup no longer matches the send path")
        return False
    if any(observed):
        Logger.error("The bot must not be registered as having spoken while the image is still being converted")
        return False
    if ctx.client.image_kwargs != [{"local_path": "fake.png", "content": None}]:
        Logger.error(f"Image upload should use local_path, got {ctx.client.image_kwargs}")
        return False
    if not state.spoken.is_set():
        Logger.error("A successfully sent message must be registered as the bot having spoken")
        return False
    return True


@func_case
async def test_qqbot_typing(tester: Tester):
    """bots.qqbot.context: 群聊输入提示的撤回时机测试"""
    await tester.test(_test_c2c_uses_native_typing, "C2C 原生输入状态测试")
    await tester.test(_test_prompt_recalled_after_bot_message, "机器人发言后撤回输入提示测试")
    await tester.test(_test_prompt_recalled_when_context_dropped, "上下文销毁后撤回输入提示测试")
    await tester.test(_test_prompt_recalled_on_repeated_start, "重复开启输入状态撤回测试")
    await tester.test(_test_no_prompt_when_message_sent_early, "窗口内已发言不补发提示测试")
    await tester.test(_test_prompt_recalled_on_end_typing, "输入状态结束撤回提示测试")
    await tester.test(_test_in_flight_prompt_recalled_after_response, "响应先于输入提示落地时的撤回测试")
    await tester.test(_test_group_typing_uses_emote_when_enabled, "开启表情后的群聊输入提示测试")
    await tester.test(_test_group_typing_omits_emote_when_disabled, "关闭表情后的群聊输入提示测试")
    await tester.test(_test_marked_after_send_succeeds, "发送成功后登记发言测试")
    await tester.test(_test_not_marked_when_send_fails, "发送失败不登记发言测试")
    await tester.test(_test_not_marked_while_converting_image, "图片转换期间不登记发言测试")

    return tester
