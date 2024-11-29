import base64
import os
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Self, Tuple, Union
from urllib import parse

import aiohttp
import filetype
from PIL import Image as PILImage
from tenacity import retry, stop_after_attempt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.builtins import MessageSession

from core.config import Config
from core.constants.default import bug_report_url_default
from core.joke import joke
from core.utils.cache import random_cache_path
from core.utils.i18n import Locale


class Plain:
    """
    文本消息。
    """

    def __init__(self,
                 text: str,
                 disable_joke: bool = False,
                 *texts: Tuple[str]):
        """
        :param text: 文本内容
        :param disable_joke: 是否禁用愚人节功能
        :param texts: 额外的文本内容
        """
        self.text = str(text)
        if not disable_joke:
            self.text = joke(self.text)
        for t in texts:
            self.text += str(t)

    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Plain(text="{self.text}")'

    def to_dict(self):
        return {'type': 'plain', 'data': {'text': self.text}}


class Url:
    """
    URL消息。
    """
    mm = False
    disable_mm = False
    md_format = False

    def __init__(self,
                 url: str,
                 use_mm: bool = False,
                 disable_mm: bool = False):
        """
        :param url: URL
        :param use_mm: 是否使用链接跳板，覆盖全局设置
        :param disable_mm: 是否禁用链接跳板，覆盖全局设置
        """
        self.url = url
        if (Url.mm and not disable_mm) or (use_mm and not Url.disable_mm):
            mm_url = f'https://mm.teahouse.team/?source=akaribot&rot13=%s'
            rot13 = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM")
            self.url = mm_url % parse.quote(parse.unquote(url).translate(rot13))

    def __str__(self):
        if Url.md_format:
            return f'[{self.url}]({self.url})'
        return self.url

    def __repr__(self):
        return f'Url(url="{self.url}")'

    def to_dict(self):
        return {'type': 'url', 'data': {'url': self.url}}


class FormattedTime:
    """
    格式化时间消息。
    """

    def __init__(self,
                 timestamp: float,
                 date: bool = True,
                 iso: bool = False,
                 time: bool = True,
                 seconds: bool = True,
                 timezone: bool = True):
        """
        :param timestamp: 时间戳（UTC时间）
        :param date: 是否显示日期
        :param iso: 是否以ISO格式显示
        :param time: 是否显示时间
        :param seconds: 是否显示秒
        :param timezone: 是否显示时区
        """
        self.timestamp = timestamp
        self.date = date
        self.iso = iso
        self.time = time
        self.seconds = seconds
        self.timezone = timezone

    def to_str(self, msg: Optional['MessageSession'] = None):
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
                datetime.fromtimestamp(
                    self.timestamp,
                    tz=timezone.utc) +
                msg.timezone_offset).strftime(
                ' '.join(ftime_template))
        else:
            ftime_template.append('%Y-%m-%d %H:%M:%S')
            return datetime.fromtimestamp(self.timestamp).strftime(' '.join(ftime_template))

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return f'FormattedTime(timestamp={self.timestamp})'

    def to_dict(self):
        return {
            'type': 'formatted_time', 'data': {'timestamp': self.timestamp}}


class I18NContext:
    """
    带有多语言的消息。
    """

    def __init__(self,
                 key: str,
                 **kwargs: Dict[str, Any]):
        """
        :param key: 多语言的键名
        :param kwargs: 多语言中的变量
        """
        self.key = key
        self.kwargs = kwargs

    def __str__(self):
        return str({'type': 'i18n', 'data': {'key': self.key, **self.kwargs}})

    def __repr__(self):
        return f'I18NContext(key="{self.key}", {", ".join(f"{k}={v}" for k, v in self.kwargs.items())})'

    def to_dict(self):
        return {'type': 'i18n', 'data': {'key': self.key, 'kwargs': self.kwargs}}


class ErrorMessage:
    """
    错误消息。
    """

    def __init__(self,
                 error_message: str,
                 locale: Optional[str] = None,
                 enable_report: bool = True,
                 **kwargs: Dict[str, Any]):
        """
        :param error_message: 错误信息文本
        :param locale: 多语言
        :param enable_report: 是否添加错误汇报部分
        :param kwargs: 多语言中的变量
        """
        self.error_message = error_message

        if locale:
            locale = Locale(locale)
            error_message = locale.t_str(error_message, **kwargs)
            self.error_message = locale.t('message.error') + error_message
            if enable_report and Config('bug_report_url', bug_report_url_default, cfg_type=str):
                self.error_message += '\n' + \
                    locale.t('error.prompt.address', url=str(Url(Config('bug_report_url', bug_report_url_default, cfg_type=str))))

    def __str__(self):
        return self.error_message

    def __repr__(self):
        return self.error_message

    def to_dict(self):
        return {'type': 'error', 'data': {'error': self.error_message}}


class Image:
    """
    图片消息。
    """

    def __init__(self,
                 path: Union[str, PILImage.Image],
                 headers: Optional[Dict[str, Any]] = None):
        """
        :param path: 图片路径或PIL.Image对象
        :param headers: 获取图片时的请求头
        """
        self.need_get = False
        self.path = path
        self.headers = headers
        if isinstance(path, PILImage.Image):
            save = f'{random_cache_path()}.png'
            path.convert('RGBA').save(save)
            self.path = save
        elif re.match('^https?://.*', path):
            self.need_get = True

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
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                raw = await req.read()
                ft = filetype.match(raw).extension
                img_path = f'{random_cache_path()}.{ft}'
                with open(img_path, 'wb+') as image_cache:
                    image_cache.write(raw)
                return img_path

    async def get_base64(self):
        file = await self.get()
        with open(file, 'rb') as f:
            return str(base64.b64encode(f.read()), "UTF-8")

    def __str__(self):
        return self.path

    def __repr__(self):
        return f'Image(path="{self.path}", headers={self.headers})'

    def to_dict(self):
        return {'type': 'image', 'data': {'path': self.path, 'headers': self.headers}}

    async def add_random_noise(self) -> Self:
        image = PILImage.open(await self.get())
        image = image.convert('RGBA')

        noise_image = PILImage.new('RGBA', (50, 50))
        for i in range(50):
            for j in range(50):
                noise_image.putpixel((i, j), (i, j, i, random.randint(0, 1)))

        image.alpha_composite(noise_image)

        save = f'{random_cache_path()}.png'
        image.save(save)
        return Image(save)


class Voice:
    """
    语音消息。
    """

    def __init__(self,
                 path: Optional[str] = None):
        """
        :param path: 语音文件路径。
        """
        self.path = path

    def __str__(self):
        return self.path

    def __repr__(self):
        return f'Voice(path={self.path})'

    def to_dict(self):
        return {'type': 'voice', 'data': {'path': self.path}}


class EmbedField:
    """
    Embed消息的字段。
    """

    def __init__(self,
                 name: Optional[str] = None,
                 value: Optional[str] = None,
                 inline: bool = False):
        """
        :param name: 字段名
        :param value: 字段值
        :param inline: 是否为行内字段
        """
        self.name = name
        self.value = value
        self.inline = inline

    def __str__(self):
        return f'{self.name}: {self.value}'

    def __repr__(self):
        return f'EmbedField(name="{self.name}", value="{self.value}", inline={self.inline})'

    def to_dict(self):
        return {'type': 'field', 'data': {'name': self.name, 'value': self.value, 'inline': self.inline}}


class Embed:
    """
    Embed消息。
    """

    def __init__(self,
                 title: Optional[str] = None,
                 description: Optional[str] = None,
                 url: Optional[str] = None,
                 timestamp: float = datetime.now().timestamp(),
                 color: int = 0x0091ff,
                 image: Optional[Image] = None,
                 thumbnail: Optional[Image] = None,
                 author: Optional[str] = None,
                 footer: Optional[str] = None,
                 fields: List[EmbedField] = []):
        """
        :param title: 标题
        :param description: 描述
        :param url: 跳转链接
        :param timestamp: 时间戳
        :param color: 颜色
        :param image: 图片
        :param thumbnail: 缩略图
        :param author: 作者
        :param footer: 页脚
        :param fields: 字段
        """
        self.title = title
        self.description = description
        self.url = url
        self.timestamp = timestamp
        self.color = color
        self.image = image
        self.thumbnail = thumbnail
        self.author = author
        self.footer = footer
        self.fields = []
        if fields:
            for f in fields:
                if isinstance(f, EmbedField):
                    self.fields.append(f)
                elif isinstance(f, dict):
                    self.fields.append(EmbedField(f['data']['name'], f['data']['value'], f['data']['inline']))
                else:
                    raise TypeError(f"Invalid type {type(f)} for EmbedField.")

    def to_message_chain(self, msg: Optional['MessageSession'] = None):
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
                    text_lst.append(f"{f.name}{msg.locale.t('message.colon')}{f.value}")
                else:
                    text_lst.append(f"{f.name}: {f.value}")
        if self.author:
            if msg:
                text_lst.append(f"{msg.locale.t('message.embed.author')}{self.author}")
            else:
                text_lst.append(f"Author: {self.author}")
        if self.footer:
            text_lst.append(self.footer)
        message_chain = []
        if text_lst:
            message_chain.append(Plain('\n'.join(text_lst)))
        if self.image:
            message_chain.append(self.image)
        return message_chain

    def __str__(self):
        return str(self.to_message_chain())

    def __repr__(self):
        return f'Embed(title="{self.title}", description="{self.description}", url="{self.url}", ' \
            f'timestamp={self.timestamp}, color={self.color}, image={self.image.__repr__()}, ' \
            f'thumbnail={self.thumbnail.__repr__()}, author="{self.author}", footer="{self.footer}", ' \
            f'fields={self.fields})'

    def to_dict(self):
        return {
            'type': 'embed',
            'data': {
                'title': self.title,
                'description': self.description,
                'url': self.url,
                'timestamp': self.timestamp,
                'color': self.color,
                'image': self.image,
                'thumbnail': self.thumbnail,
                'author': self.author,
                'footer': self.footer,
                'fields': [f.to_dict() for f in self.fields]}}


__all__ = ["Plain", "Image", "Voice", "Embed", "EmbedField", "Url", "ErrorMessage", "FormattedTime", "I18NContext"]
