"""QQBot 媒体预上传的瞬态重试与实际消息发送边界。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from botpy.protocol import ApiError, MediaFileType, MessageType, TransportError

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_c2c_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import AudioElement, ImageElement, PlainElement, VideoElement
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


def _client(uploads, sends=None):
    return SimpleNamespace(
        upload_media=AsyncMock(side_effect=uploads),
        send=AsyncMock(side_effect=sends, return_value={"id": "sent-media"}),
        send_markdown=AsyncMock(return_value={"id": "sent-markdown"}),
    )


def _transport(cause=None, *, attempts=1):
    return TransportError("media request failed", cause=cause, attempts=attempts)


def _image_message():
    return MessageChain.assign(ImageElement.assign(__file__))


async def _send(client, message, delays, *, target_from=target_group_prefix, markdown=False):
    session = SessionInfo(
        target_id=f"{target_from}|upload-retry-target",
        sender_id="QQBot|upload-retry-sender",
        target_from=target_from,
        client_name="QQBot",
        session_id="qqbot-upload-retry",
        message_id="source-message",
        support_markdown=markdown,
    )
    original_sleep = asyncio.sleep

    async def skip_backoff(delay):
        if delay:
            delays.append(delay)
        else:
            await original_sleep(0)

    with (
        patch.object(QQBotContextManager, "client", client),
        patch.object(QQBotContextManager, "context", {session.session_id: object()}),
        patch.object(QQBotContextManager, "typing_states", {}),
        patch.object(QQBotContextManager, "message_send_queues", {}),
        patch.object(QQBotContextManager, "_shutting_down", False),
        patch.object(qqbot_context, "qq_use_markdown", markdown),
        patch.object(qqbot_context, "resolve_media_path", AsyncMock(side_effect=lambda element: element.path)),
        patch.object(qqbot_context.asyncio, "sleep", skip_backoff),
    ):
        return await QQBotContextManager.send_message(session, message, quote=False)


def _assert_upload_calls(client, file_types, scope="group"):
    assert client.upload_media.await_count == len(file_types)
    for upload, file_type in zip(client.upload_media.await_args_list, file_types):
        target, actual_type = upload.args
        assert (target.scope, target.target_id, target.message_id) == (
            scope,
            "upload-retry-target",
            "source-message",
        )
        assert actual_type == file_type
        assert upload.kwargs == {"local_path": __file__, "srv_send_msg": False}


async def _test_c2c_single_image_uses_plain_upload_once():
    client = _client([{"file_info": "image"}])
    delays = []
    result = await _send(client, _image_message(), delays, target_from=target_c2c_prefix, markdown=True)
    assert result == ["sent-media"]
    assert delays == []
    client.upload_media.assert_awaited_once()
    client.send.assert_awaited_once()
    client.send_markdown.assert_not_awaited()
    assert client.send.await_args.kwargs["msg_type"] == MessageType.MEDIA
    assert client.send.await_args.kwargs["media"] == {"file_info": "image"}
    return True


async def _test_group_media_retry_prepares_everything_before_send():
    failures = [
        _transport(httpx.ReadTimeout("read stalled")),
        _transport(httpx.ConnectError("connection reset")),
        _transport(httpx.RemoteProtocolError("peer disconnected")),
    ]
    client = _client(
        [failures[0], {"file_info": "image"}, failures[1], {"file_info": "audio"}, failures[2], {"file_info": "video"}]
    )

    async def send_after_upload(target, **kwargs):
        assert client.upload_media.await_count == 6
        return {"id": kwargs["media"]["file_info"]}

    client.send.side_effect = send_after_upload
    message = MessageChain.assign(
        [ImageElement.assign(__file__), AudioElement.assign(__file__), VideoElement.assign(__file__)]
    )
    delays = []
    assert await _send(client, message, delays) == ["image", "audio", "video"]
    assert delays == [1, 1, 1]
    _assert_upload_calls(
        client,
        [MediaFileType.IMAGE] * 2 + [MediaFileType.VOICE] * 2 + [MediaFileType.VIDEO] * 2,
    )
    assert client.send.await_count == 3
    assert [entry.kwargs["media"] for entry in client.send.await_args_list] == [
        {"file_info": "image"},
        {"file_info": "audio"},
        {"file_info": "video"},
    ]
    return True


async def _test_upload_exhaustion_preserves_error_without_sending():
    failures = [_transport(httpx.WriteTimeout(f"attempt {attempt}")) for attempt in range(3)]
    client = _client(failures)
    delays = []
    try:
        await _send(client, _image_message(), delays)
    except TransportError as error:
        assert error is failures[-1]
        assert error.cause is failures[-1].cause
    else:
        raise AssertionError("Upload exhaustion must propagate the original transport error")
    assert delays == [1, 2]
    _assert_upload_calls(client, [MediaFileType.IMAGE] * 3)
    client.send.assert_not_awaited()
    client.send_markdown.assert_not_awaited()
    return True


async def _test_sdk_attempts_count_toward_upload_limit():
    for attempts, remaining_failures, expected_delays in ((3, [], []), (2, [1], [2])):
        failures = [_transport(httpx.ConnectTimeout("SDK timed out"), attempts=attempts)]
        failures.extend(
            _transport(httpx.ConnectTimeout("retry timed out"), attempts=value) for value in remaining_failures
        )
        client = _client(failures)
        delays = []
        try:
            await _send(client, _image_message(), delays)
        except TransportError as error:
            assert error is failures[-1]
        else:
            raise AssertionError("SDK attempts must exhaust the shared upload attempt limit")
        assert delays == expected_delays
        assert client.upload_media.await_count == len(failures)
        client.send.assert_not_awaited()
    return True


async def _test_nontransient_upload_errors_are_not_retried():
    errors = [
        ApiError("bad media", status=400, code=40001),
        ValueError("invalid local path"),
        RuntimeError("file preparation failed"),
        _transport(ValueError("invalid local data")),
        _transport(httpx.LocalProtocolError("invalid request")),
        _transport(httpx.UnsupportedProtocol("unsupported URL")),
        _transport(),
    ]
    for expected_error in errors:
        client = _client([expected_error, {"file_info": "must-not-retry"}])
        delays = []
        try:
            await _send(client, _image_message(), delays)
        except Exception as error:
            assert error is expected_error
        else:
            raise AssertionError(f"{type(expected_error).__name__} must propagate without retry")
        assert delays == []
        client.upload_media.assert_awaited_once()
        client.send.assert_not_awaited()
    return True


async def _test_cancelled_upload_propagates_immediately():
    cancelled = asyncio.CancelledError("upload cancelled")
    client = _client([cancelled, {"file_info": "must-not-retry"}])
    delays = []
    try:
        await _send(client, _image_message(), delays)
    except asyncio.CancelledError as error:
        assert error is cancelled
    else:
        raise AssertionError("Upload cancellation must propagate")
    assert delays == []
    client.upload_media.assert_awaited_once()
    client.send.assert_not_awaited()
    return True


async def _test_invalid_upload_response_never_sends_or_retries():
    for response in (None, {}, {"file_info": ""}):
        client = _client([response, {"file_info": "must-not-retry"}])
        delays = []
        try:
            await _send(client, _image_message(), delays)
        except RuntimeError as error:
            assert "file_info" in str(error)
        else:
            raise AssertionError("An upload without file_info cannot be sent")
        assert delays == []
        client.upload_media.assert_awaited_once()
        client.send.assert_not_awaited()
    return True


async def _test_send_transport_failure_is_retried_with_same_kwargs():
    failure = _transport(httpx.ReadTimeout("send response lost"))
    client = _client([{"file_info": "image"}], sends=[failure, {"id": "sent-after-retry"}])
    delays = []
    result = await _send(client, _image_message(), delays)
    assert result == ["sent-after-retry"]
    assert delays == [qqbot_context.MESSAGE_SEND_RETRY_INITIAL_DELAY]
    client.upload_media.assert_awaited_once()
    assert client.send.await_count == 2
    first_call, second_call = client.send.await_args_list
    assert first_call.kwargs == second_call.kwargs
    return True


async def _test_partial_send_retries_and_preserves_ids():
    failure = _transport(httpx.WriteTimeout("second send stalled"))
    client = _client(
        [{"file_info": "first"}, {"file_info": "second"}],
        sends=[{"id": "first-image"}, failure, {"id": "second-image"}],
    )
    message = MessageChain.assign(
        [PlainElement.assign("caption"), ImageElement.assign(__file__), ImageElement.assign(__file__)]
    )
    delays = []
    assert await _send(client, message, delays) == ["first-image", "second-image"]
    assert delays == [qqbot_context.MESSAGE_SEND_RETRY_INITIAL_DELAY]
    assert client.upload_media.await_count == 2
    assert client.send.await_count == 3
    return True


@func_case
async def test_qqbot_upload_retry(tester: Tester):
    await tester.test(_test_c2c_single_image_uses_plain_upload_once, "C2C Markdown 单图走普通上传且只发一次")
    await tester.test(_test_group_media_retry_prepares_everything_before_send, "群图片与音视频重试预上传完成后依次发送")
    await tester.test(_test_upload_exhaustion_preserves_error_without_sending, "上传重试耗尽后保留原始异常且不发送")
    await tester.test(_test_sdk_attempts_count_toward_upload_limit, "SDK 内部尝试次数计入上传重试上限")
    await tester.test(_test_nontransient_upload_errors_are_not_retried, "API、本地与非瞬态传输错误不重试")
    await tester.test(_test_cancelled_upload_propagates_immediately, "上传取消立即传播且不重试")
    await tester.test(_test_invalid_upload_response_never_sends_or_retries, "缺少 file_info 的上传结果不重试或发送")
    await tester.test(_test_send_transport_failure_is_retried_with_same_kwargs, "消息发送阶段瞬态错误沿用同一请求重试")
    await tester.test(_test_partial_send_retries_and_preserves_ids, "部分发送失败重试后保留已发送 ID")
    return tester
