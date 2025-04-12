from __future__ import annotations

import base64
import os
import random
import re
from datetime import datetime, UTC
from typing import Optional, TYPE_CHECKING, Dict, Any, Union, List
from urllib import parse

import httpx
from PIL import Image as PILImage
from attrs import define
from filetype import filetype
from tenacity import retry, stop_after_attempt

from core.config import Config
from core.constants import bug_report_url_default
from core.constants.info import Info
from core.i18n import Locale
from core.utils.cache import random_cache_path

from copy import deepcopy

if TYPE_CHECKING:
    from core.builtins import MessageSession


class MessageElement:

    @classmethod
    def __name__(cls):
        return cls.__name__


@define
class PlainElement(MessageElement):
    """
    文本元素。

    :param text: 文本。
    """

    text: str
    disable_joke: bool

    @classmethod
    def assign(cls, *texts: Any, disable_joke: bool = False):
        """
        :param texts: 文本内容。
        :param disable_joke: 是否禁用玩笑功能。（默认为False）
        """
        text = "".join([str(x) for x in texts])
        disable_joke = bool(disable_joke)
        return deepcopy(cls(text=text, disable_joke=disable_joke))


@define
class URLElement(MessageElement):
    """
    URL元素。

    :param url: URL。
    """

    url: str
    md_format = Info.use_url_md_format

    @classmethod
    def assign(cls, url: str, use_mm: bool = False):
        """
        :param url: URL。
        :param use_mm: 是否使用链接跳板，覆盖全局设置。（默认为False）
        """
        if Info.use_url_manager and use_mm:
            mm_url = "https://mm.teahouse.team/?source=akaribot&rot13=%s"
            rot13 = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM",
            )
            url = mm_url % parse.quote(parse.unquote(url).translate(rot13))

        return deepcopy(cls(url=url))

    def __str__(self):
        if self.md_format:
            return f"[{self.url}]({self.url})"
        return self.url


@define
class FormattedTimeElement(MessageElement):
    """
    格式化时间消息。

    :param timestamp: UTC时间戳。
    """

    timestamp: float
    date: bool = True
    iso: bool = False
    time: bool = True
    seconds: bool = True
    timezone: bool = True

    def to_str(self, msg: Optional[MessageSession] = None):
        ftime_template = []
        if msg:
            if self.date:
                if self.iso:
                    ftime_template.append(msg.locale.t("time.date.iso.format"))
                else:
                    ftime_template.append(msg.locale.t("time.date.format"))
            if self.time:
                if self.seconds:
                    ftime_template.append(msg.locale.t("time.time.format"))
                else:
                    ftime_template.append(msg.locale.t("time.time.nosec.format"))
            if self.timezone:
                if msg._tz_offset == "+0":
                    ftime_template.append("(UTC)")
                else:
                    ftime_template.append(f"(UTC{msg._tz_offset})")

            return (
                datetime.fromtimestamp(self.timestamp, tz=UTC)
                + msg.timezone_offset
            ).strftime(" ".join(ftime_template))
        ftime_template.append("%Y-%m-%d %H:%M:%S")
        return datetime.fromtimestamp(self.timestamp).strftime(" ".join(ftime_template))

    def __str__(self):
        return self.to_str()

    @classmethod
    def assign(
        cls,
        timestamp: float,
        date: bool = True,
        iso: bool = False,
        time: bool = True,
        seconds: bool = True,
        timezone: bool = True,
    ):
        """
        :param timestamp: UTC时间戳。
        :param date: 是否显示日期。（默认为True）
        :param iso: 是否以ISO格式显示。（默认为False）
        :param time: 是否显示时间。（默认为True）
        :param seconds: 是否显示秒。（默认为True）
        :param timezone: 是否显示时区。（默认为True）
        """
        return deepcopy(
            cls(
                timestamp=timestamp,
                date=date,
                iso=iso,
                time=time,
                seconds=seconds,
                timezone=timezone,
            )
        )


@define
class I18NContextElement(MessageElement):
    """
    带有多语言的消息。
    """

    key: str
    disable_joke: bool
    kwargs: Dict[str, Any]

    @classmethod
    def assign(cls, key: str, disable_joke: bool = False, **kwargs: Any):
        """
        :param key: 多语言的键名。
        :param kwargs: 多语言中的变量。
        """
        return deepcopy(cls(key=key, disable_joke=disable_joke, kwargs=kwargs))


@define
class ImageElement(MessageElement):
    """
    图片消息。

    :param path: 图片路径。
    """

    path: str
    need_get: bool = False
    headers: Optional[Dict[str, Any]] = None

    @classmethod
    def assign(
        cls, path: Union[str, PILImage.Image], headers: Optional[Dict[str, Any]] = None
    ):
        """
        :param path: 图片路径。
        :param headers: 获取图片时的请求头。
        """
        need_get = False
        if isinstance(path, PILImage.Image):
            save = f"{random_cache_path()}.png"
            path.convert("RGBA").save(save)
            path = save
        elif re.match("^https?://.*", path):
            need_get = True
        return deepcopy(cls(path, need_get, headers))

    async def get(self):
        """
        获取图片。
        """
        if self.need_get:
            return os.path.abspath(await self.get_image())
        return os.path.abspath(self.path)

    @retry(stop=stop_after_attempt(3))
    async def get_image(self):
        """
        从网络下载图片。
        """
        url = self.path
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=20.0)
            raw = resp.content
            ft = filetype.match(raw).extension
            img_path = f"{random_cache_path()}.{ft}"
            with open(img_path, "wb+") as image_cache:
                image_cache.write(raw)
            return img_path

    async def get_base64(self):
        file = await self.get()
        with open(file, "rb") as f:
            return str(base64.b64encode(f.read()), "UTF-8")

    async def add_random_noise(self) -> "ImageElement":
        image = PILImage.open(await self.get())
        image = image.convert("RGBA")

        noise_image = PILImage.new("RGBA", (50, 50))
        for i in range(50):
            for j in range(50):
                noise_image.putpixel((i, j), (i, j, i, random.randint(0, 1)))

        image.alpha_composite(noise_image)

        save = f"{random_cache_path()}.png"
        image.save(save)
        return ImageElement.assign(save)


@define
class VoiceElement(MessageElement):
    """
    语音消息。

    :param path: 语音路径。
    """

    path: str

    @classmethod
    def assign(cls, path: str):
        """
        :param path: 语音路径。
        """
        return deepcopy(cls(path))


@define
class MentionElement(MessageElement):
    """
    提及元素。

    :param id: 提及用户ID。
    :param client: 平台。
    """

    client: str
    id: str

    @classmethod
    def assign(cls, user_id: str):
        """
        :param user_id: 用户id。
        """
        return deepcopy(cls(client=user_id.split("|")[0], id=user_id.split("|")[-1]))


@define
class EmbedFieldElement(MessageElement):
    """
    Embed字段。

    :param name: 字段名。
    :param value: 字段值。
    :param inline: 是否内联。（默认为False）
    """

    name: str
    value: str
    inline: bool = False

    @classmethod
    def assign(cls, name: str, value: str, inline: bool = False):
        """
        :param name: 字段名。
        :param value: 字段值。
        :param inline: 是否内联。（默认为False）
        """
        return deepcopy(cls(name=name, value=value, inline=inline))


@define
class EmbedElement(MessageElement):
    """
    Embed消息。
    :param title: 标题。
    :param description: 描述。
    :param url: 跳转 URL。
    :param color: 颜色。
    :param image: 图片。
    :param thumbnail: 缩略图。
    :param author: 作者。
    :param footer: 页脚。
    :param fields: 字段。
    """

    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    timestamp: float = datetime.now().timestamp()
    color: int = 0x0091FF
    image: Optional[ImageElement] = None
    thumbnail: Optional[ImageElement] = None
    author: Optional[str] = None
    footer: Optional[str] = None
    fields: Optional[List[EmbedFieldElement]] = None

    @classmethod
    def assign(
        cls,
        title: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        timestamp: float = datetime.now().timestamp(),
        color: int = 0x0091FF,
        image: Optional[ImageElement] = None,
        thumbnail: Optional[ImageElement] = None,
        author: Optional[str] = None,
        footer: Optional[str] = None,
        fields: Optional[List[EmbedFieldElement]] = None,
    ):
        return deepcopy(
            cls(
                title=title,
                description=description,
                url=url,
                timestamp=timestamp,
                color=color,
                image=image,
                thumbnail=thumbnail,
                author=author,
                footer=footer,
                fields=fields,
            )
        )

    def to_message_chain(self, msg: Optional[MessageSession] = None):
        """
        将Embed转换为消息链。
        """
        text_lst = []
        if self.title:
            text_lst.append(self.title)
        if self.description:
            text_lst.append(self.description)
        if self.url:
            text_lst.append(self.url)
        if self.fields:
            for f in self.fields:
                if msg:
                    text_lst.append(f"{msg.locale.t_str(f.name)}{msg.locale.t(
                        "message.colon")}{msg.locale.t_str(f.value)}")
                else:
                    text_lst.append(f"{f.name}: {f.value}")
        if self.author:
            if msg:
                text_lst.append(f"{msg.locale.t("message.embed.author")}{msg.locale.t_str(self.author)}")
            else:
                text_lst.append(f"Author: {self.author}")
        if self.footer:
            if msg:
                text_lst.append(msg.locale.t_str(self.footer))
            else:
                text_lst.append(self.footer)
        message_chain = []
        if text_lst:
            message_chain.append(PlainElement.assign("\n".join(text_lst)))
        if self.image:
            message_chain.append(self.image)
        return message_chain

    def __str__(self):
        return str(self.to_message_chain())


elements_map = {
    x.__name__: x
    for x in [
        PlainElement,
        URLElement,
        FormattedTimeElement,
        I18NContextElement,
        ImageElement,
        VoiceElement,
        EmbedFieldElement,
        EmbedElement,
        MentionElement,
    ]
}
__all__ = [
    "MessageElement",
    "PlainElement",
    "URLElement",
    "FormattedTimeElement",
    "I18NContextElement",
    "ImageElement",
    "VoiceElement",
    "EmbedFieldElement",
    "EmbedElement",
    "MentionElement",
    "elements_map",
]
