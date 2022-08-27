from typing import List

from PIL import Image as PImage

from core.elements import Image


async def image_split(i: Image) -> List[Image]:
    i = PImage.open(await i.get())
    iw, ih = i.size
    if ih <= 1500:
        return [Image(i)]
    _h = 0
    i_list = []
    for x in range((ih // 1500) + 1):
        if _h + 1500 > ih:
            crop_h = ih
        else:
            crop_h = _h + 1500
        i_list.append(Image(i.crop((0, _h, iw, crop_h))))
        _h = crop_h
    return i_list
