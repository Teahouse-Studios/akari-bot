"""真实发送路径的出站规范化、观察隔离与取消边界。"""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext, Plain
from core.builtins.parser.hooks import HookPoint, OutgoingPayload, ParserHookExecutor, build_subscription
from core.builtins.parser.hooks import dispatch as hook_dispatch
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.constants.exceptions import SendMessageFailed, SessionFinished, WaitCancelException
from core.queue.contracts import PlatformAPI
from core.tester import Tester, func_case
from core.types import Module
from core.types.module.component_meta import HookMeta

_PATHS = ("send_message", "send_direct_message", "send_private_message")
_RESULT_POINTS = (HookPoint.OUTGOING_SENT, HookPoint.OUTGOING_FAILED)


@contextmanager
def _sending(path, handlers, platform_effect):
    module_name = "__outgoing_regression"
    module = Module.assign(module_name=module_name, alias=None, recommend_modules=None, developers=None)
    module._db_load = True
    module.load = True
    manager = SimpleNamespace(
        modules={module_name: module},
        parser_hook_subscriptions={
            point: [
                build_subscription(
                    module_name,
                    HookMeta(function=handler, point=point, name=point.value, timeout=0),
                    0,
                )
            ]
            for point, handler in handlers.items()
        },
    )
    msg = MessageSession(
        SessionInfo(
            target_id="TEST|Group|outgoing",
            target_from="TEST|Group",
            client_name="TEST",
            sender_id="TEST|outgoing",
            support_private_msg=True,
            require_enable_modules=False,
        )
    )
    platform = AsyncMock(side_effect=platform_effect)
    method = "send_private_msg" if path == "send_private_message" else "send_message"
    replacement = SimpleNamespace(submit=platform) if path == "send_direct_message" else platform
    with (
        patch.object(hook_dispatch, "_executor", ParserHookExecutor(manager)),
        patch.object(PlatformAPI, method, replacement),
    ):
        yield msg, platform


async def _test_observers_see_normalized_chain():
    original_is_safe = MessageChain.is_safe.fget
    for path in _PATHS:
        for rewrite_kind in ("text", "nodes", "unsafe"):
            sent = []
            observed = []
            failure = RuntimeError("submission failed") if path == "send_direct_message" else None

            async def rewrite(ctx):
                ctx.outgoing.quote = False
                if rewrite_kind == "nodes":
                    ctx.outgoing.chain = MessageNodes.assign([MessageChain.assign("node")])
                else:
                    ctx.outgoing.chain = "unsafe rewrite" if rewrite_kind == "unsafe" else "rewritten text"

            async def observe(ctx):
                observed.append(
                    (
                        ctx.point,
                        ctx.outgoing.chain.to_kecode(),
                        ctx.outgoing.quote,
                        ctx.outgoing.chain is sent[0],
                        list(ctx.outgoing.message_ids) if ctx.outgoing.message_ids is not None else None,
                    )
                )
                ctx.outgoing.chain.values.clear()
                if ctx.outgoing.message_ids is not None:
                    ctx.outgoing.message_ids.clear()

            async def platform_effect(*args, **kwargs):
                sent.append(args[2] if path == "send_private_message" else args[1])
                if path != "send_private_message":
                    assert kwargs["quote"] is False
                if failure:
                    raise failure
                return ["sent-id"]

            handlers = {HookPoint.OUTGOING_BEFORE_SEND: rewrite, **dict.fromkeys(_RESULT_POINTS, observe)}
            with (
                _sending(path, handlers, platform_effect) as (msg, platform),
                patch(
                    "core.utils.image.msgnode2image",
                    new=AsyncMock(return_value=Plain("rendered node", disable_joke=True)),
                ),
                patch.object(
                    MessageChain,
                    "is_safe",
                    property(lambda chain: chain.to_str() != "unsafe rewrite" and original_is_safe(chain)),
                ),
            ):
                try:
                    result = await getattr(msg, path)("original")
                except RuntimeError as exc:
                    assert exc is failure
                else:
                    assert failure is None
                    assert (result.message_id if path == "send_message" else result) == ["sent-id"]
                platform.assert_awaited_once()

            assert len(observed) == 1
            assert observed[0] == (
                HookPoint.OUTGOING_FAILED if failure else HookPoint.OUTGOING_SENT,
                sent[0].to_kecode(),
                False,
                False,
                None if failure else ["sent-id"],
            )
            if rewrite_kind == "unsafe":
                assert sent[0].to_kecode() == MessageChain.assign(I18NContext("error.message.chain.unsafe")).to_kecode()
            else:
                assert sent[0].to_str() == ("rendered node" if rewrite_kind == "nodes" else "rewritten text")
    return True


async def _test_observer_faults_preserve_platform_result():
    snapshot = OutgoingPayload.snapshot
    dispatch = hook_dispatch.dispatch_parser_hook
    for path in _PATHS:
        for platform_result in ("success", "empty", "error"):
            if path == "send_direct_message" and platform_result == "empty":
                continue
            for fault_stage in ("snapshot", "dispatch", "observer"):
                for fault_type in (RuntimeError, SessionFinished, WaitCancelException, SendMessageFailed):
                    platform_done = False
                    original_error = RuntimeError("original platform error")
                    result_ids = ["sent-id"] if platform_result == "success" else []
                    fault = fault_type("observer fault")
                    observed = []

                    async def observer(ctx):
                        observed.append(ctx.point)
                        if fault_stage == "observer":
                            raise fault

                    def observe_snapshot(payload):
                        if platform_done and fault_stage == "snapshot":
                            raise fault
                        return snapshot(payload)

                    async def observe_dispatch(point, *args, **kwargs):
                        if point in _RESULT_POINTS and fault_stage == "dispatch":
                            raise fault
                        return await dispatch(point, *args, **kwargs)

                    async def platform_effect(*args, **kwargs):
                        nonlocal platform_done
                        platform_done = True
                        if platform_result == "error":
                            raise original_error
                        return result_ids

                    with (
                        _sending(path, dict.fromkeys(_RESULT_POINTS, observer), platform_effect) as (msg, platform),
                        patch.object(OutgoingPayload, "snapshot", observe_snapshot),
                        patch.object(hook_dispatch, "dispatch_parser_hook", observe_dispatch),
                    ):
                        try:
                            result = await getattr(msg, path)("message")
                        except BaseException as exc:
                            assert platform_result == "error" and exc is original_error
                        else:
                            assert platform_result != "error"
                            if path == "send_message":
                                assert result.message_id == result_ids
                            elif path == "send_private_message":
                                assert result is result_ids
                            else:
                                assert result is None
                                assert observed == []
                        platform.assert_awaited_once()
                        assert not hook_dispatch._outgoing_observing.get()
                        expected_observation = (
                            [HookPoint.OUTGOING_SENT if platform_result == "success" else HookPoint.OUTGOING_FAILED]
                            if fault_stage == "observer"
                            and not (path == "send_direct_message" and platform_result == "success")
                            else []
                        )
                        assert observed == expected_observation
    return True


async def _test_outgoing_cancellation_and_exit_propagate():
    dispatch = hook_dispatch.dispatch_parser_hook
    for path in _PATHS:
        for signal_type in (asyncio.CancelledError, SystemExit, KeyboardInterrupt):
            for stage in ("platform", "snapshot", "dispatch"):
                if path == "send_direct_message" and stage != "platform":
                    continue
                signal = signal_type()
                observer_calls = []

                async def observer(ctx):
                    observer_calls.append(ctx.point)

                async def platform_effect(*args, **kwargs):
                    if stage == "platform":
                        raise signal
                    return ["sent-id"]

                def snapshot(payload):
                    if stage == "snapshot":
                        raise signal
                    return original_snapshot(payload)

                async def observe_dispatch(point, *args, **kwargs):
                    if point in _RESULT_POINTS and stage == "dispatch":
                        raise signal
                    return await dispatch(point, *args, **kwargs)

                original_snapshot = OutgoingPayload.snapshot
                with (
                    _sending(path, dict.fromkeys(_RESULT_POINTS, observer), platform_effect) as (msg, platform),
                    patch.object(OutgoingPayload, "snapshot", snapshot),
                    patch.object(hook_dispatch, "dispatch_parser_hook", observe_dispatch),
                ):
                    try:
                        await getattr(msg, path)("message")
                    except BaseException as exc:
                        assert exc is signal
                    else:
                        raise AssertionError("Cancellation/exit was swallowed")
                    assert observer_calls == []
                    platform.assert_awaited_once()
                    assert not hook_dispatch._outgoing_observing.get()
    return True


async def _test_external_cancel_during_outgoing_observer():
    for path in ("send_message", "send_private_message"):
        observing = asyncio.Event()

        async def observer(ctx):
            observing.set()
            await asyncio.Event().wait()

        with _sending(path, {HookPoint.OUTGOING_SENT: observer}, AsyncMock(return_value=["sent-id"])) as (
            msg,
            platform,
        ):
            task = asyncio.create_task(getattr(msg, path)("message"))
            try:
                await asyncio.wait_for(observing.wait(), timeout=1)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                else:
                    raise AssertionError("Task cancellation was swallowed")
                platform.assert_awaited_once()
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    return True


@func_case
async def test_outgoing_hooks(tester: Tester):
    await tester.test(_test_observers_see_normalized_chain, "三条发送路径观察最终规范化内容")
    await tester.test(_test_observer_faults_preserve_platform_result, "出站观察故障保留平台真实结果")
    await tester.test(_test_outgoing_cancellation_and_exit_propagate, "出站取消与进程退出信号传播")
    await tester.test(_test_external_cancel_during_outgoing_observer, "慢出站观察者响应外部任务取消")
    return tester
