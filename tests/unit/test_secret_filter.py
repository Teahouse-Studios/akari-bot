"""发送链路敏感信息拦截测试：元素覆盖与各出站路径。"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.elements import EmbedElement, URLElement
from core.builtins.message.internal import (
    ActionText,
    Button,
    ButtonFrame,
    ButtonRows,
    I18NContext,
    Markdown,
    Plain,
    Raw,
)
from core.builtins.parser.hooks import ParserHookExecutor
from core.builtins.parser.hooks import dispatch as hook_dispatch
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants import Secret
from core.queue.contracts import PlatformAPI
from core.tester import Tester, func_case

SECRET = "TEST-SECRET-9F3A"
UNSAFE_KECODE = MessageChain.assign(I18NContext("error.message.chain.unsafe")).to_kecode()


@contextmanager
def _secret_registered(value: str = SECRET):
    saved = set(Secret.data)
    Secret.add(value)
    try:
        yield value
    finally:
        Secret.data.clear()
        Secret.data.update(saved)


def _make_session_info() -> SessionInfo:
    return SessionInfo(
        target_id="TEST|Group|secret",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|secret",
        support_private_msg=True,
        require_enable_modules=False,
    )


@contextmanager
def _patched_hooks():
    manager = SimpleNamespace(modules={}, parser_hook_subscriptions={})
    with patch.object(hook_dispatch, "_executor", ParserHookExecutor(manager)):
        yield


def _leaking_chains():
    return {
        "plain": MessageChain.assign(Plain(f"ip {SECRET}")),
        "markdown": MessageChain.assign(Markdown(f"ip {SECRET}")),
        "url": MessageChain.assign(URLElement.assign(f"https://example.com/{SECRET}")),
        "embed": MessageChain.assign(EmbedElement.assign(title="t", description=f"ip {SECRET}")),
        "i18n": MessageChain.assign(I18NContext("error.message.chain.empty", value=SECRET)),
        "i18n-nested-chain": MessageChain.assign(
            I18NContext("error.message.chain.empty", value=MessageChain.assign(f"ip {SECRET}"))
        ),
        "action-text": MessageChain.assign(ActionText(f"ip {SECRET}")),
        "action-show": MessageChain.assign(ActionText("echo", show=f"ip {SECRET}")),
        "button": MessageChain.assign(Button(f"ip {SECRET}", "cb")),
        "button-frame": MessageChain.assign(ButtonFrame([ButtonRows.assign([Button(f"ip {SECRET}", "cb")])])),
        "raw": MessageChain.assign(Raw(f"ip {SECRET}")),
    }


def _test_is_safe_covers_rendered_elements():
    try:
        if not MessageChain.assign("Hello").is_safe:
            return False
        with _secret_registered():
            if not all(not chain.is_safe for chain in _leaking_chains().values()):
                return False
            nodes = MessageNodes.assign([MessageChain.assign(f"ip {SECRET}")])
            return not nodes.is_safe
    except Exception:
        return False


async def _test_send_message_replaces_leaking_chains():
    session = MessageSession(_make_session_info())
    try:
        with _patched_hooks(), _secret_registered():
            for label, chain in _leaking_chains().items():
                sent = []

                async def platform(_session_info, message, **kwargs):
                    sent.append(message)
                    return ["id"]

                with patch.object(PlatformAPI, "send_message", AsyncMock(side_effect=platform)):
                    await session.send_message(chain, quote=False)
                if len(sent) != 1 or sent[0].to_kecode() != UNSAFE_KECODE:
                    return False

            # 显式关闭检查时保持原有放行语义
            sent = []

            async def allow_platform(_session_info, message, **kwargs):
                sent.append(message)
                return ["id"]

            with patch.object(PlatformAPI, "send_message", AsyncMock(side_effect=allow_platform)):
                await session.send_message(Plain(f"ip {SECRET}"), disable_secret_check=True)
            return len(sent) == 1 and SECRET in sent[0].to_kecode()
    except Exception:
        return False


async def _test_post_message_replaces_leaking_chains():
    session_info = _make_session_info()
    try:
        with _patched_hooks(), _secret_registered():
            for label, chain in _leaking_chains().items():
                posted = []
                platform = SimpleNamespace(
                    submit=AsyncMock(side_effect=lambda _s, m, _n="": posted.append(m) or ["id"])
                )
                with (
                    patch.object(Bot, "pick_channel_heads", AsyncMock(return_value=[session_info])),
                    patch("core.builtins.bot.enable_analytics", False),
                    patch.object(PlatformAPI, "post_message", platform),
                ):
                    await Bot.post_message("test", chain, session_list=[session_info])
                if len(posted) != 1 or posted[0].to_kecode() != UNSAFE_KECODE:
                    return False
            return True
    except Exception:
        return False


async def _test_bot_send_private_message_replaces_leaking_chains():
    session_info = _make_session_info()
    try:
        with _patched_hooks(), _secret_registered():
            for label, chain in _leaking_chains().items():
                sent = []

                async def platform(_session_info, _user_id, message):
                    sent.append(message)
                    return ["id"]

                with patch.object(PlatformAPI, "send_private_msg", AsyncMock(side_effect=platform)):
                    await Bot.send_private_message(session_info, chain)
                if len(sent) != 1 or sent[0].to_kecode() != UNSAFE_KECODE:
                    return False
            return True
    except Exception:
        return False


def _test_secret_update_registers_batch():
    saved = set(Secret.data)
    try:
        Secret.data.clear()
        Secret.update(["batch-one", "batch-two"])
        return Secret.check("contains batch-one") and Secret.check("contains batch-two")
    finally:
        Secret.data.clear()
        Secret.data.update(saved)


@func_case
async def test_secret_filter(tester: Tester):
    """发送链路敏感信息拦截测试"""
    await tester.test(_test_is_safe_covers_rendered_elements, "is_safe 覆盖全部会渲染文本的元素")
    await tester.test(_test_send_message_replaces_leaking_chains, "send_message 拦截敏感信息并保留显式放行")
    await tester.test(_test_post_message_replaces_leaking_chains, "post_message 拦截敏感信息")
    await tester.test(_test_bot_send_private_message_replaces_leaking_chains, "Bot.send_private_message 拦截敏感信息")
    await tester.test(_test_secret_update_registers_batch, "Secret.update 登记批量密钥")
    return tester
