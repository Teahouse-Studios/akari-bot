"""轻量图片切分工具，避免平台适配器加载完整 WebRender 链路。"""

from PIL import Image as PILImage

from core.builtins.message.elements import ImageElement


async def image_split(image: ImageElement, max_height: int = 1500) -> list[ImageElement]:
    """按最大高度切分图片，并及时释放 Pillow 图像资源。"""
    if max_height <= 0:
        raise ValueError("max_height must be positive")

    with PILImage.open(await image.get()) as source:
        width, height = source.size
        if height <= max_height:
            with source.copy() as copied:
                return [ImageElement.assign(copied)]

        images = []
        for top in range(0, height, max_height):
            with source.crop((0, top, width, min(top + max_height, height))) as cropped:
                images.append(ImageElement.assign(cropped))
        return images
