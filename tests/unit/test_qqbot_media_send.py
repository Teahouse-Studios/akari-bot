"""QQBot 媒体消息的预上传与发送边界。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from botpy.protocol import MediaFileType, MessageType, TransportError

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import QQBotContextManager
from bots.qqbot.info import target_c2c_prefix, target_group_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import AudioElement, ImageElement, VideoElement
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


def _client(uploads, sends=None):
    return SimpleNamespace(
        upload_media=AsyncMock(side_effect=uploads),
        send=AsyncMock(side_effect=sends, return_value={"id": "sent-media"}),
    )


def _image_message():
    return MessageChain.assign(ImageElement.assign(__file__))


async def _send(client, message, *, target_from=target_group_prefix, markdown=False):
    session = SessionInfo(
        target_id=f"{target_from}|media-send-target",
        sender_id="QQBot|media-send-sender",
        target_from=target_from,
        client_name="QQBot",
        session_id="qqbot-media-send",
        message_id="source-message",
        support_markdown=markdown,
    )
    with (
        patch.object(QQBotContextManager, "client", client),
        patch.object(QQBotContextManager, "context", {session.session_id: object()}),
        patch.object(QQBotContextManager, "typing_states", {}),
        patch.object(QQBotContextManager, "message_send_queues", {}),
        patch.object(QQBotContextManager, "_shutting_down", False),
        patch.object(qqbot_context, "qq_use_markdown", markdown),
        patch.object(qqbot_context, "resolve_media_path", AsyncMock(side_effect=lambda element: element.path)),
        patch.object(qqbot_context, "_convert_qqbot_image", side_effect=lambda path: path),
    ):
        return await QQBotContextManager.send_message(session, message, quote=False)


def _assert_upload_calls(client, file_types, scope="group"):
    assert client.upload_media.await_count == len(file_types)
    for upload, file_type in zip(client.upload_media.await_args_list, file_types):
        target, actual_type = upload.args
        assert (target.scope, target.target_id, target.message_id) == (
            scope,
            "media-send-target",
            "source-message",
        )
        assert actual_type == file_type
        assert upload.kwargs == {"local_path": __file__, "srv_send_msg": False}


async def _test_c2c_single_image_uses_plain_upload_once():
    client = _client([{"file_info": "image"}])
    result = await _send(client, _image_message(), target_from=target_c2c_prefix, markdown=True)
    assert result == ["sent-media"]
    client.upload_media.assert_awaited_once()
    client.send.assert_awaited_once()
    assert client.send.await_args.kwargs["msg_type"] == MessageType.MEDIA
    assert client.send.await_args.kwargs["media"] == {"file_info": "image"}
    return True


async def _test_group_media_prepares_everything_before_send():
    client = _client([{"file_info": "image"}, {"file_info": "audio"}, {"file_info": "video"}])

    async def send_after_upload(target, **kwargs):
        assert client.upload_media.await_count == 3
        return {"id": kwargs["media"]["file_info"]}

    client.send.side_effect = send_after_upload
    message = MessageChain.assign(
        [ImageElement.assign(__file__), AudioElement.assign(__file__), VideoElement.assign(__file__)]
    )
    assert await _send(client, message) == ["image", "audio", "video"]
    _assert_upload_calls(client, [MediaFileType.IMAGE, MediaFileType.VOICE, MediaFileType.VIDEO])
    assert [entry.kwargs["media"] for entry in client.send.await_args_list] == [
        {"file_info": "image"},
        {"file_info": "audio"},
        {"file_info": "video"},
    ]
    return True


async def _test_upload_failure_propagates_without_sending():
    failure = TransportError("media request failed", cause=httpx.ReadTimeout("read stalled"), attempts=2)
    client = _client([failure])
    try:
        await _send(client, _image_message())
    except TransportError as error:
        assert error is failure
    else:
        raise AssertionError("Upload failure must propagate to the caller")
    client.upload_media.assert_awaited_once()
    client.send.assert_not_awaited()
    return True


async def _test_invalid_upload_response_never_sends():
    for response in (None, {}, {"file_info": ""}):
        client = _client([response])
        try:
            await _send(client, _image_message())
        except RuntimeError as error:
            assert "file_info" in str(error)
        else:
            raise AssertionError("An upload without file_info cannot be sent")
        client.upload_media.assert_awaited_once()
        client.send.assert_not_awaited()
    return True


@func_case
async def test_qqbot_media_send(tester: Tester):
    await tester.test(_test_c2c_single_image_uses_plain_upload_once, "C2C Markdown 单图走普通上传且只发一次")
    await tester.test(_test_group_media_prepares_everything_before_send, "群媒体预上传完成后依次发送")
    await tester.test(_test_upload_failure_propagates_without_sending, "上传失败直接上抛且不发送")
    await tester.test(_test_invalid_upload_response_never_sends, "缺少 file_info 的上传结果不发送")
    return tester
