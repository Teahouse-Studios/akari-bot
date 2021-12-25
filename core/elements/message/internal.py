import re
import uuid
from os.path import abspath
from typing import List

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


class EmbedField:
    def __init__(self,
                 name: str = None,
                 value: str = None,
                 inline: bool = False):
        self.name = name
        self.value = value
        self.inline = inline


class Embed:
    def __init__(self,
                 title: str = None,
                 description: str = None,
                 url: str = None,
                 timestamp: float = None,
                 color: int = None,
                 # image: Image = None,
                 # thumbnail: Image = None,
                 author: str = None,
                 footer: str = None,
                 fields: List[EmbedField] = None):
        self.title = title
        self.description = description
        self.url = url
        self.timestamp = timestamp
        self.color = color
        # self.image = image
        # self.thumbnail = thumbnail
        self.author = author
        self.footer = footer
        self.fields = fields

    def to_msgchain(self):
        text_lst = []
        if self.title is not None:
            text_lst.append(self.title)
        if self.description is not None:
            text_lst.append(self.description)
        if self.url is not None:
            text_lst.append(self.url)
        if self.fields is not None:
            for f in self.fields:
                if f.inline:
                    text_lst.append(f"{f.name}: {f.value}")
                else:
                    text_lst.append(f"{f.name}:\n{f.value}")
        if self.author is not None:
            text_lst.append("作者：" + self.author)
        if self.footer is not None:
            text_lst.append(self.footer)
        msgchain = []
        if text_lst:
            msgchain.append(Plain('\n'.join(text_lst)))
        # if self.image is not None:
        #    msgchain.append(self.image)
        return msgchain


__all__ = ["Plain", "Image", "Voice", "Embed", "EmbedField"]
