"""Shared declarations drive both directions, including real domain values."""

import inspect
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from attrs import define

from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.message.internal import I18NContext
from core.builtins.session.context import ContextManager
from core.builtins.session.features import Features
from core.builtins.session.info import FetchedSessionInfo, SessionInfo
from core.queue import codec
from core.queue.base import JobQueueBase
from core.queue.contracts import PlatformAPI, ServerAPI
from core.queue.rpc import context_method, remote
from core.tester import Tester, func_case


def _wire(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


async def _test_arguments_and_native_results():
    @remote("test.signature")
    async def method(user: str, count: int = 2, *, enabled: bool = False) -> list[str]: ...

    class Peer(JobQueueBase):
        @classmethod
        async def call(cls, target, name, payload, *, timeout=None):
            assert target == "Server" and name == method.name and timeout == 120
            return _wire(await cls.handlers[name](_wire(payload)))

    @method.bind(Peer)
    async def handler(user: str, count: int = 2, *, enabled: bool = False) -> list[str]:
        return [user] * count if enabled else []

    assert await method.using(Peer)("用户") == []
    assert await method.using(Peer)("用户", enabled=True) == ["用户", "用户"]
    assert inspect.signature(method).parameters["count"].default == 2
    for args, kwargs in [((1,), {}), (("x",), {"count": "2"}), ((), {}), (("x",), {"unknown": True})]:
        try:
            method.encode_arguments(*args, **kwargs)
        except TypeError:
            pass
        else:
            raise AssertionError("Invalid arguments were accepted")
    try:
        method.bind(Peer)(handler)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate handler was accepted")
    return True


async def _test_domain_codec_roundtrip():
    session = await FetchedSessionInfo.assign(
        target_id="RPC-CODEC|Group|1", target_from="RPC-CODEC", client_name="RPC-CODEC", fetch=True
    )
    message = MessageChain.assign([I18NContext("error.message.report", command="codec")])
    payload = PlatformAPI.send_message.encode_arguments(session, message, quote=False)
    bound = PlatformAPI.send_message.decode_arguments(_wire(payload))
    restored = bound.arguments["session_info"]
    assert isinstance(restored, SessionInfo) and restored.fetch
    assert restored.target_id == session.target_id
    assert isinstance(bound.arguments["message"], MessageChain)
    assert bound.arguments["message"].to_list() == message.to_list()
    assert bound.arguments["quote"] is False
    nodes = MessageNodes([message])
    restored_nodes = codec.decode(_wire(codec.encode(nodes, MessageChain | MessageNodes)), MessageChain | MessageNodes)
    assert isinstance(restored_nodes, MessageNodes)
    assert codec.encode(restored_nodes, MessageChain | MessageNodes) == codec.encode(nodes, MessageChain | MessageNodes)
    features = Features(support_image=True, support_private_msg=True)
    restored_features = ServerAPI.keepalive.decode_arguments(
        _wire(ServerAPI.keepalive.encode_arguments("RPC-CODEC", ctx_slot_index=0, features=features))
    ).arguments
    assert restored_features["ctx_slot_index"] == 0
    assert restored_features["features"] == features
    return True


async def _test_dynamic_hook_values_are_safe_and_lossless():
    # Dictionaries resembling codec metadata remain ordinary dictionaries.
    data = {"kind": "object", "type": "untrusted.module", "value": [None, False, {}, []]}
    message = MessageChain.assign("dynamic message")
    payload = ServerAPI.trigger_hook.encode_arguments("example", nested={"message": message, "data": data})
    restored = ServerAPI.trigger_hook.decode_arguments(_wire(payload)).arguments
    assert isinstance(restored["kwargs"]["nested"]["message"], MessageChain)
    assert restored["kwargs"]["nested"]["data"] == data
    for value in [False, None, [], {}, "", 0]:
        assert codec.decode(_wire(codec.encode(value, Any)), Any) == value
    for value, annotation in [(object(), Any), (lambda: None, Any), ("wrong", dict), ({}, list)]:
        try:
            codec.encode(value, annotation)
        except TypeError:
            pass
        else:
            raise AssertionError("Non-contract value was encoded")
    try:
        codec.decode({"kind": "object", "type": "untrusted.module", "value": {}}, Any)
    except TypeError:
        pass
    else:
        raise AssertionError("Unregistered type was decoded")
    return True


async def _test_platform_signature_drives_automatic_dispatch():
    method = context_method(ContextManager.restrict_member)
    assert method.signature == inspect.signature(ContextManager.restrict_member)

    class Peer(JobQueueBase):
        pass

    class Context:
        restrict_member = AsyncMock(return_value=None)

    session = await SessionInfo.assign(target_id="RPC-AUTO|Group|1", target_from="RPC-AUTO", client_name="RPC-AUTO")
    resolver = AsyncMock(return_value=Context)
    method.bind_context(Peer, resolver)
    value = await Peer.handlers[method.name](_wire(method.encode_arguments(session, ["RPC-AUTO|1"], reason="test")))
    assert value is None and resolver.await_count == 1
    args = Context.restrict_member.await_args
    assert args.args[0].target_id == session.target_id
    assert args.args[1:] == (["RPC-AUTO|1"], None, "test")
    return True


async def _test_submission_and_signature_drift():
    @remote("test.submit", target="other", timeout=7)
    async def method(value: int) -> None: ...

    class Peer(JobQueueBase):
        pass

    submit = AsyncMock(return_value="accepted-id")
    call = AsyncMock()
    with patch.object(Peer, "submit", submit), patch.object(Peer, "call", call):
        assert await method.using(Peer).submit(4) == "accepted-id"
        submit.assert_awaited_once_with("other", "test.submit", {"value": 4}, timeout=7)
        call.assert_not_awaited()

    async def wrong(value: int, extra: int) -> None: ...

    try:
        method.bind(Peer)(wrong)
    except TypeError:
        return True
    raise AssertionError("Handler signature drift was accepted")


async def _test_union_discriminators_and_dictionary_contracts():
    @define
    class Number:
        value: int

    @define
    class Text:
        value: str

    for value in (Number(4), Text("four"), None):
        annotation = Number | Text | None
        result = codec.decode(_wire(codec.encode(value, annotation)), annotation)
        assert type(result) is type(value) and result == value
    try:

        @remote("test.invalid_dictionary")
        async def invalid(value: dict[int, str]) -> None: ...
    except TypeError:
        pass
    else:
        raise AssertionError("Non-string JSON dictionary key declaration accepted")
    return True


async def _test_error_reporting_deduplicates_delivery_failures():
    from core.exports import exports
    from core.queue import reporting, server

    session = await FetchedSessionInfo.assign(
        target_id="RPC-REPORT|Group|1", target_from="RPC-REPORT", client_name="RPC-REPORT", fetch=True
    )
    bot = SimpleNamespace(
        fetch_union_target_list=AsyncMock(return_value=[session]),
        pick_channel_heads=AsyncMock(return_value=[session]),
    )
    send = AsyncMock(return_value="report-task")
    previous = dict(server._recent_reports)
    server._recent_reports.clear()
    try:
        with (
            patch.dict(exports, {"Bot": bot}),
            patch.object(server, "CoreConfig", SimpleNamespace(report_targets=["report-union"])),
            patch.object(ServerAPI.direct_message, "submit", send),
        ):
            await server.report_error("platform.send_message", "delivery failed")
            await server.report_error("platform.send_message", "delivery failed")
        assert send.await_count == 1
        assert send.await_args.args[0] is session
        assert send.await_args.kwargs == {"disable_secret_check": True}
        submit = AsyncMock(return_value="task")
        with (
            patch.object(reporting, "CoreConfig", SimpleNamespace(report_targets=["report-union"])),
            patch.object(ServerAPI.report_error, "using", return_value=SimpleNamespace(submit=submit)),
        ):
            await reporting.report_rpc_error(object(), "platform.broken", "trace")
            await reporting.report_rpc_error(object(), ServerAPI.report_error.name, "report failed")
        submit.assert_awaited_once_with("platform.broken", "trace")
        return True
    finally:
        server._recent_reports.clear()
        server._recent_reports.update(previous)


async def _test_server_queries_encode_real_module_metadata():
    from core.queue import server

    for method, handler, arguments, expected in [
        (ServerAPI.get_modules_list, server.get_modules_list, (), list),
        (ServerAPI.get_modules_info, server.get_modules_info, (), dict),
        (ServerAPI.get_module_helpdoc, server.get_module_helpdoc, ("wiki",), dict),
        (ServerAPI.get_module_related, server.get_module_related, ("wiki",), list),
    ]:
        result = await method.dispatch(handler, _wire(method.encode_arguments(*arguments)))
        decoded = codec.decode(_wire(result), method.result_type)
        assert isinstance(decoded, expected)
        if method is ServerAPI.get_module_helpdoc:
            assert decoded["module_name"] == "wiki" and "commands" in decoded
    return True


@func_case
async def test_rpc_contracts(tester: Tester):
    await tester.test(_test_server_queries_encode_real_module_metadata, "真实模块查询结果经过共享契约和 JSON 编解码")
    await tester.test(_test_arguments_and_native_results, "RPC 签名绑定、默认值、参数校验与原生返回值")
    await tester.test(_test_domain_codec_roundtrip, "会话、消息节点、i18n 和平台特性的 JSON 往返")
    await tester.test(_test_dynamic_hook_values_are_safe_and_lossless, "动态 hook 参数无损往返和类型白名单")
    await tester.test(_test_platform_signature_drives_automatic_dispatch, "平台接口复用 ContextManager 签名并自动分发")
    await tester.test(_test_submission_and_signature_drift, "仅提交操作与执行等待分离并拒绝签名漂移")
    await tester.test(_test_union_discriminators_and_dictionary_contracts, "联合类型显式保留分支并拒绝非字符串字典键")
    await tester.test(
        _test_error_reporting_deduplicates_delivery_failures, "配置错误报告保留并阻断重复发送失败的报告循环"
    )
    return tester
