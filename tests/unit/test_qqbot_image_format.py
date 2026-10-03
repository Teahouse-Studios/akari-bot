from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from PIL import Image as PILImage
from botpy.protocol import MediaFileType, MessageType

import bots.qqbot.context as qqbot_context
from bots.qqbot.context import QQBotContextManager, _convert_qqbot_image
from bots.qqbot.info import target_c2c_prefix, target_direct_prefix, target_group_prefix, target_guild_prefix
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ImageElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.tester import Tester, func_case


@contextmanager
def _image_files():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with patch.object(qqbot_context, "random_cache_path", side_effect=lambda ext: root / f"{uuid4()}.{ext}"):
            yield root


def _save_image(path, image_format, *, mode="RGB", color="red"):
    with PILImage.new(mode, (32, 24), color) as image:
        options = {"lossless": True} if image_format == "WEBP" else {}
        image.save(path, format=image_format, **options)


def _assert_jpeg(path):
    assert Path(path).suffix == ".jpg"
    with PILImage.open(path) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.size == (32, 24)


async def _send(client, message, *, target_from=target_group_prefix, markdown=False):
    session = SessionInfo(
        target_id=f"{target_from}|image-format-target",
        sender_id="QQBot|image-format-sender",
        target_from=target_from,
        client_name="QQBot",
        session_id="qqbot-image-format",
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
    ):
        return await QQBotContextManager.send_message(session, message, quote=False)


def _test_supported_images_are_unchanged():
    with _image_files() as root:
        for image_format, extension in (("PNG", "png"), ("JPEG", "jpg"), ("JPEG", "JPEG")):
            path = root / f"image.{extension}"
            _save_image(path, image_format)
            original = path.read_bytes()
            assert _convert_qqbot_image(str(path)) == str(path)
            assert path.read_bytes() == original

        gif = root / "animated.gif"
        with PILImage.new("RGB", (32, 24), "red") as first, PILImage.new("RGB", (32, 24), "blue") as second:
            first.save(gif, save_all=True, append_images=[second], duration=100, loop=0)
        original = gif.read_bytes()
        assert _convert_qqbot_image(str(gif)) == str(gif)
        assert gif.read_bytes() == original
        with PILImage.open(gif) as image:
            assert image.n_frames == 2
    return True


def _test_unsupported_images_use_jpeg_content():
    with _image_files() as root:
        for image_format, extension in (("WEBP", "webp"), ("WEBP", "jpg"), ("BMP", "bmp"), ("TIFF", "tiff")):
            path = root / f"{image_format}.{extension}"
            _save_image(path, image_format)
            original = path.read_bytes()
            output = _convert_qqbot_image(str(path))
            assert output != str(path)
            _assert_jpeg(output)
            assert path.read_bytes() == original
    return True


def _test_transparency_uses_white_background():
    with _image_files() as root:
        for image_format, mode, color in (
            ("WEBP", "RGBA", (255, 0, 0, 0)),
            ("TIFF", "RGBA", (255, 0, 0, 0)),
            ("TIFF", "LA", (0, 0)),
        ):
            path = root / f"transparent-{image_format}-{mode}"
            _save_image(path, image_format, mode=mode, color=color)
            output = _convert_qqbot_image(str(path))
            _assert_jpeg(output)
            with PILImage.open(output) as image:
                assert image.getpixel((16, 12)) == (255, 255, 255)
    return True


def _test_animated_webp_uses_first_frame():
    with _image_files() as root:
        path = root / "animated.webp"
        with PILImage.new("RGB", (32, 24), "red") as first, PILImage.new("RGB", (32, 24), "blue") as second:
            first.save(path, format="WEBP", save_all=True, append_images=[second], duration=100, loop=0, lossless=True)
        output = _convert_qqbot_image(str(path))
        _assert_jpeg(output)
        with PILImage.open(output) as image:
            red, green, blue = image.getpixel((16, 12))
            assert red > 240 and green < 10 and blue < 10
            assert not getattr(image, "is_animated", False)
    return True


def _test_supported_content_gets_matching_extension():
    with _image_files() as root:
        for image_format, expected_extension in (("PNG", ".png"), ("JPEG", ".jpg"), ("GIF", ".gif")):
            path = root / f"{image_format}.webp"
            _save_image(path, image_format)
            original = path.read_bytes()
            output = Path(_convert_qqbot_image(str(path)))
            assert output.suffix == expected_extension
            assert output.read_bytes() == original
            assert path.read_bytes() == original
    return True


async def _test_plain_send_uploads_converted_images():
    with _image_files() as root:
        path = root / "image.webp"
        _save_image(path, "WEBP")
        for target_from in (target_group_prefix, target_c2c_prefix, target_guild_prefix, target_direct_prefix):

            async def upload(target, file_type, *, local_path, srv_send_msg):
                assert file_type == MediaFileType.IMAGE
                assert not srv_send_msg
                _assert_jpeg(local_path)
                return {"file_info": "converted"}

            async def send(target, **kwargs):
                if target.scope in ("group", "c2c"):
                    assert kwargs["media"] == {"file_info": "converted"}
                else:
                    _assert_jpeg(kwargs["extra"]["file_image"])
                return {"id": "sent"}

            client = SimpleNamespace(upload_media=AsyncMock(side_effect=upload), send=AsyncMock(side_effect=send))
            message = MessageChain.assign(ImageElement.assign(path))
            assert await _send(client, message, target_from=target_from) == ["sent"]
            client.send.assert_awaited_once()
            assert client.upload_media.await_count == (
                1 if target_from in (target_group_prefix, target_c2c_prefix) else 0
            )
    return True


async def _test_markdown_and_s3_use_converted_image():
    with _image_files() as root:
        path = root / "image.webp"
        _save_image(path, "WEBP")
        for fallback in (False, True):
            uploaded_paths = []

            async def upload(target, file_type, *, local_path):
                assert file_type == MediaFileType.IMAGE
                _assert_jpeg(local_path)
                uploaded_paths.append(local_path)
                if fallback:
                    raise RuntimeError("raw URL unavailable")
                return SimpleNamespace(raw_url="https://example.com/image?token=test")

            async def upload_s3(local_path):
                assert uploaded_paths == [local_path]
                _assert_jpeg(local_path)
                return {"public_url": "https://example.com/fallback.jpg"}

            client = SimpleNamespace(
                upload_media_url=AsyncMock(side_effect=upload),
                upload_media=AsyncMock(),
                send=AsyncMock(return_value={"id": "sent"}),
            )
            storage = SimpleNamespace(upload_temp=AsyncMock(side_effect=upload_s3))
            message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(path)])
            with patch.object(qqbot_context, "_load_s3_storage", return_value=storage):
                assert await _send(client, message, markdown=True) == ["sent"]
            client.upload_media_url.assert_awaited_once()
            client.upload_media.assert_not_awaited()
            assert storage.upload_temp.await_count == (1 if fallback else 0)
            kwargs = client.send.await_args.kwargs
            assert kwargs["msg_type"] == MessageType.MARKDOWN
            expected_url = (
                "https://example.com/fallback.jpg"
                if fallback
                else "https://example.com/image?token=test&response-content-type=image%2Fjpeg"
            )
            assert kwargs["markdown"]["content"] == f"hello\n![text #32px #24px]({expected_url})"
    return True


async def _test_downloaded_image_is_resolved_once():
    with _image_files() as root:
        path = root / "downloaded.webp"
        _save_image(path, "WEBP")
        client = SimpleNamespace(
            upload_media_url=AsyncMock(return_value=SimpleNamespace(raw_url="https://example.com/image")),
            send=AsyncMock(return_value={"id": "sent"}),
        )
        message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign("https://example.com/image")])
        with patch.object(ImageElement, "get_image", new=AsyncMock(return_value=path)) as download:
            assert await _send(client, message, markdown=True) == ["sent"]
            download.assert_awaited_once()
        _assert_jpeg(client.upload_media_url.await_args.kwargs["local_path"])
    return True


async def _test_bad_image_and_conversion_failure_are_skipped():
    with _image_files() as root:
        bad_image = root / "bad.jpg"
        bad_image.write_bytes(b"invalid image")
        source = root / "image.webp"
        _save_image(source, "WEBP")
        for markdown in (False, True):
            client = SimpleNamespace(
                upload_media=AsyncMock(),
                upload_media_url=AsyncMock(),
                send=AsyncMock(return_value={"id": "sent"}),
            )
            message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(bad_image)])
            assert await _send(client, message, markdown=markdown) == ["sent"]
            client.upload_media.assert_not_awaited()
            client.upload_media_url.assert_not_awaited()
            kwargs = client.send.await_args.kwargs
            assert (kwargs["markdown"]["content"] if markdown else kwargs["content"]) == "hello"

        output = root / "failed.jpg"

        def fail_save(image, path, **kwargs):
            Path(path).write_bytes(b"partial JPEG")
            raise OSError("encoding failed")

        message = MessageChain.assign([PlainElement.assign("hello"), ImageElement.assign(source)])
        with (
            patch.object(qqbot_context, "random_cache_path", return_value=output),
            patch.object(PILImage.Image, "save", side_effect=fail_save, autospec=True),
        ):
            assert await _send(client, message) == ["sent"]
        assert not output.exists()
        client.upload_media.assert_not_awaited()
        with PILImage.open(source) as image:
            assert image.format == "WEBP"
    return True


@func_case
async def test_qqbot_image_format(tester: Tester):
    await tester.test(_test_supported_images_are_unchanged, "PNG、JPEG 和 GIF 保留原始内容及动画")
    await tester.test(_test_unsupported_images_use_jpeg_content, "不支持的图片按实际内容转为 JPG")
    await tester.test(_test_transparency_uses_white_background, "透明图片转 JPG 使用白色背景")
    await tester.test(_test_animated_webp_uses_first_frame, "动态 WebP 转 JPG 使用首帧")
    await tester.test(_test_supported_content_gets_matching_extension, "支持格式的图片校正后缀并保留内容")
    await tester.test(_test_plain_send_uploads_converted_images, "普通图片发送覆盖群聊、C2C、频道和频道私信")
    await tester.test(_test_markdown_and_s3_use_converted_image, "Markdown 上传及 S3 回退使用转换后的 JPG")
    await tester.test(_test_downloaded_image_is_resolved_once, "Markdown 网络图片下载一次并使用本地尺寸")
    await tester.test(_test_bad_image_and_conversion_failure_are_skipped, "损坏图片和转换失败不上传且保留文本")
    return tester
