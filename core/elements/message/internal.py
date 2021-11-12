import re
import uuid
from os.path import abspath

import aiohttp
import filetype
from PIL import Image as PImage
from aiohttp_retry import ExponentialRetry, RetryClient

from config import CachePath


class Plain:
    def __init__(self,
                 text):
        self.text = text


class Image:
    def __init__(self,
                 path):
        self.need_get = False
        self.path = path
        if isinstance(path, PImage.Image):
            savepath = f'{CachePath}{str(uuid.uuid4())}.jpg'
            path.convert('RGB').save(savepath)
            self.path = savepath
        elif re.match('^https?://.*', path):
            self.need_get = True

    async def get(self):
        if self.need_get:
            return abspath(await self.get_image(self.path))
        return abspath(self.path)

    async def get_image(self, url, headers=None):
        async with RetryClient(retry_options=ExponentialRetry(attempts=3)) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                raw = await req.read()
                ft = filetype.match(raw).extension
                img_path = f'{CachePath}{str(uuid.uuid4())}.{ft}'
                with open(img_path, 'wb+') as image_cache:
                    image_cache.write(raw)
                return img_path


class Voice:
    def __init__(self,
                 path=None):
        self.path = path


__all__ = ["Plain", "Image", "Voice"]
