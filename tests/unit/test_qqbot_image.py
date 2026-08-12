from bots.qqbot.context import MARKDOWN_IMAGE_MAX_WIDTH, _markdown_image_size
from core.builtins.message.elements import ImageElement
from core.tester import Tester, func_case


def _test_default_markdown_image_width():
    return _markdown_image_size(ImageElement.assign("test.png"), 2000, 1000) == (MARKDOWN_IMAGE_MAX_WIDTH, 64)


def _test_custom_markdown_image_width():
    return _markdown_image_size(ImageElement.assign("test.png", max_h=512), 2000, 1000) == (512, 256)


def _test_small_markdown_image_is_not_upscaled():
    return _markdown_image_size(ImageElement.assign("test.png", max_h=512), 320, 160) == (320, 160)


@func_case
async def test_qqbot_image(tester: Tester):
    """QQBot Markdown 图片尺寸。"""
    await tester.test(_test_default_markdown_image_width, "QQBot Markdown 图片默认宽度测试")
    await tester.test(_test_custom_markdown_image_width, "QQBot Markdown 图片自定义宽度测试")
    await tester.test(_test_small_markdown_image_is_not_upscaled, "QQBot Markdown 小图不放大测试")
    return tester
