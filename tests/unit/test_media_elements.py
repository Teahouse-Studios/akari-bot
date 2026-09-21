"""媒体元素读写与 media 工具错误语义单元测试。"""

import base64
import os
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image as PILImage
from tenacity import RetryError

from core.builtins.message.elements import AudioElement, ImageElement, VideoElement
from core.tester import Tester, func_case
from core.utils.media import resolve_media_base64, resolve_media_path


def _inner_exception(error: BaseException) -> BaseException:
    while isinstance(error, RetryError):
        inner = error.last_attempt.exception()
        if inner is None:
            break
        error = inner
    return error


def _png_bytes() -> bytes:
    buffer = BytesIO()
    PILImage.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    return buffer.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, content: bytes):
        self.content = content

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, *_args, **_kwargs):
        return _FakeResponse(self.content)


async def _test_image_element_missing_file_raises() -> bool:
    try:
        await ImageElement.assign("missing-image-fixture.png").get()
    except FileNotFoundError:
        return True
    return False


async def _test_image_element_get_image_accepts_png() -> bool:
    content = _png_bytes()
    with patch("core.builtins.message.elements.httpx.AsyncClient", return_value=_FakeClient(content)):
        path = await ImageElement.assign("https://example.com/image.png").get()
    try:
        return Path(path).is_file() and Path(path).read_bytes() == content
    finally:
        Path(path).unlink(missing_ok=True)


async def _test_image_element_get_image_rejects_non_image() -> bool:
    client = _FakeClient(b"<html>hotlink protection</html>")
    with patch("core.builtins.message.elements.httpx.AsyncClient", return_value=client):
        try:
            await ImageElement.assign("https://example.com/blocked.png").get()
        except Exception as error:
            # get_image 带重试装饰器，最内层异常为格式校验失败
            return isinstance(_inner_exception(error), ValueError)
    return False


async def _test_resolve_media_path_for_local_image() -> bool:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        image_file.write(_png_bytes())
        image_path = image_file.name
    try:
        return await resolve_media_path(ImageElement.assign(image_path)) == image_path
    finally:
        os.unlink(image_path)


async def _test_resolve_media_path_skips_missing_image() -> bool:
    return await resolve_media_path(ImageElement.assign("missing-image-fixture.png")) is None


async def _test_resolve_media_path_skips_failed_download() -> bool:
    element = ImageElement.assign("https://example.com/blocked.png")
    with patch(
        "core.builtins.message.elements.ImageElement.get",
        new=AsyncMock(side_effect=ValueError("not a recognized image file")),
    ):
        return await resolve_media_path(element) is None


async def _test_resolve_media_path_for_local_media_files() -> bool:
    created = []
    try:
        for element_type, suffix in ((AudioElement, ".mp3"), (VideoElement, ".mp4")):
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as media_file:
                media_file.write(b"media fixture")
                media_path = media_file.name
            created.append(media_path)
            if await resolve_media_path(element_type.assign(media_path)) != media_path:
                return False
        return True
    finally:
        for media_path in created:
            os.unlink(media_path)


async def _test_resolve_media_path_skips_missing_or_empty_media_files() -> bool:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as empty_file:
        empty_path = empty_file.name
    try:
        return (
            await resolve_media_path(AudioElement.assign("missing-audio-fixture.mp3")) is None
            and await resolve_media_path(VideoElement.assign(empty_path)) is None
        )
    finally:
        os.unlink(empty_path)


async def _test_resolve_media_base64_encodes_file_content() -> bool:
    content = _png_bytes()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        image_file.write(content)
        image_path = image_file.name
    try:
        encoded = await resolve_media_base64(ImageElement.assign(image_path))
        return encoded == base64.b64encode(content).decode("UTF-8")
    finally:
        os.unlink(image_path)


async def _test_resolve_media_base64_returns_none_for_unavailable_media() -> bool:
    return (
        await resolve_media_base64(ImageElement.assign("missing-image-fixture.png")) is None
        and await resolve_media_base64(AudioElement.assign("missing-audio-fixture.mp3")) is None
    )


@func_case
async def test_media_elements(tester: Tester):
    """媒体元素与 media 工具的错误语义。"""
    await tester.test(_test_image_element_missing_file_raises, "本地图片缺失时 ImageElement.get 抛出 FileNotFoundError")
    await tester.test(_test_image_element_get_image_accepts_png, "响应体为图片时下载落盘")
    await tester.test(_test_image_element_get_image_rejects_non_image, "响应体非图片时下载失败且不落盘")
    await tester.test(_test_resolve_media_path_for_local_image, "resolve_media_path 解析本地图片")
    await tester.test(_test_resolve_media_path_skips_missing_image, "resolve_media_path 跳过缺失图片")
    await tester.test(_test_resolve_media_path_skips_failed_download, "resolve_media_path 跳过下载失败图片")
    await tester.test(_test_resolve_media_path_for_local_media_files, "resolve_media_path 解析本地音视频")
    await tester.test(
        _test_resolve_media_path_skips_missing_or_empty_media_files, "resolve_media_path 跳过缺失或空音视频"
    )
    await tester.test(_test_resolve_media_base64_encodes_file_content, "resolve_media_base64 编码文件内容")
    await tester.test(
        _test_resolve_media_base64_returns_none_for_unavailable_media, "resolve_media_base64 对不可用元素返回 None"
    )
    return tester
