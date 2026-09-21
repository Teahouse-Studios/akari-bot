"""消息元素模块 - 定义各种类型的消息元素。"""

from __future__ import annotations

import base64
import html
import mimetypes
import random
import re
from copy import deepcopy
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib import parse

import httpx
import orjson
from PIL import Image as PILImage
from attrs import define
from filetype import filetype
from tenacity import retry, stop_after_attempt

from core.i18n import safe_strftime
from core.logger import Logger
from core.utils.cache import random_cache_path

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo


class BaseElement:
    """消息元素基类。"""

    @classmethod
    def __name__(cls):
        """
        获取元素类名。

        :return: 类的名称字符串
        """
        return cls.__name__

    def kecode(self):
        """转换为 KE 码格式（AkariBot 特定的消息格式）。

        :return: KE 码格式的字符串
        :raises NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    def __str__(self):
        """转换为字符串表示。

        :return: 字符串表示
        :raises NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError


@define
class PlainElement(BaseElement):
    """纯文本元素 - 用于表示消息中的纯文本内容。"""

    text: str
    disable_joke: bool = False
    allow_parse: bool = True

    @classmethod
    def assign(cls, *texts: Any, disable_joke: bool = False, allow_parse: bool = True):
        """创建纯文本元素的工厂方法。

        :param texts: 文本内容（支持多个参数），每个参数会被转换为字符串并拼接
        :param disable_joke: 是否禁用玩笑功能（默认为 False）
        :param allow_parse: 是否允许解析 KE 码、i18n 与平台消息标记（默认为 True）
        :return: PlainElement 实例
        """
        text = "".join([str(x) for x in texts])
        disable_joke = bool(disable_joke)
        return deepcopy(cls(text=text, disable_joke=disable_joke, allow_parse=bool(allow_parse)))

    def kecode(self):
        """转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        encoded = parse.quote(self.text, safe="")
        params = [f"text={encoded}"]
        if self.disable_joke:
            params.append("disable_joke=1")
        if not self.allow_parse:
            params.append("allow_parse=0")
        return f"[KE:plain,{','.join(params)}]"

    def __str__(self):
        """返回文本内容"""
        return self.text


def markdown_to_plain_text(text: str) -> str:
    """把常见 Markdown 标记转换为适合纯文本平台展示的内容。"""
    lines = []
    fence_char = None
    fence_length = 0

    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})(.*)$", stripped)
        if fence:
            marker, info = fence.groups()
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
                if info := info.strip():
                    lines.append(info)
                continue
            if marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
                continue

        if fence_char is not None:
            lines.append(line)
            continue

        # Markdown 表格的分隔行没有可读内容，纯文本降级时直接丢弃。
        if re.fullmatch(r"\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*", line):
            continue

        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", line)
        line = re.sub(r"^\s{0,3}>\s?", "", line)
        line = re.sub(r"^\s*[-*+]\s+\[[xX]\]\s+", "☑ ", line)
        line = re.sub(r"^\s*[-*+]\s+\[ \]\s+", "☐ ", line)
        line = re.sub(r"^\s*[-*+]\s+", "• ", line)
        if re.fullmatch(r"\s{0,3}(?:[-*_]\s*){3,}", line):
            continue

        stripped_line = line.strip()
        if stripped_line.startswith("|") and stripped_line.endswith("|"):
            cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", stripped_line[1:-1])]
            line = " | ".join(cells)

        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(
        r"!\[([^\]]*)\]\((\S+?)(?:\s+[\"'].*?[\"'])?\)",
        lambda match: f"{match.group(1)} ({match.group(2)})" if match.group(1) else match.group(2),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\((\S+?)(?:\s+[\"'].*?[\"'])?\)",
        lambda match: match.group(2) if match.group(1) == match.group(2) else f"{match.group(1)} ({match.group(2)})",
        text,
    )
    text = re.sub(r"<((?:https?://|mailto:)[^>]+)>", r"\1", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"(`+)(.*?)\1", r"\2", text)
    text = re.sub(r"~~(.*?)~~", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>|~])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html.unescape(text).strip()


@define
class MarkdownElement(PlainElement):
    """Markdown 文本元素；不支持 Markdown 时可降级为普通文本。"""

    def to_plain(self) -> PlainElement:
        """移除 Markdown 标记并保留可读内容。"""
        return PlainElement.assign(
            markdown_to_plain_text(self.text),
            disable_joke=self.disable_joke,
            allow_parse=self.allow_parse,
        )

    def kecode(self):
        """转换为可跨进程传输的 Markdown KE 码。"""
        encoded = parse.quote(self.text, safe="")
        params = [f"text={encoded}"]
        if self.disable_joke:
            params.append("disable_joke=1")
        if not self.allow_parse:
            params.append("allow_parse=0")
        return f"[KE:markdown,{','.join(params)}]"


@define
class URLElement(BaseElement):
    """URL 链接元素 - 用于在消息中包含链接。"""

    original_url: str
    url: str
    trusted: bool | None = None
    applied_md_format: bool = False
    md_format_name: str | None = None

    @classmethod
    def assign(cls, url: str, trusted: bool | None = None, md_format: bool = False, md_format_name: str | None = None):
        """创建 URL 元素的工厂方法。

        :param url: URL 地址
        :param trusted: 链接是否已在代码中认证
                       None 表示未表态，由会话的 URLManager 设置决定（默认）
                       True 表示已认证，一律不作未认证处理
                       False 表示显式不可信，强制作未认证处理
        :param md_format: 是否使用 Markdown 格式（默认为 False）
                         True 表示转换为 [名称](URL) 格式
        :param md_format_name: Markdown 格式的链接名称（默认为 None，使用 URL 本身）
        :return: URLElement 实例
        """
        original_url = url
        # 须判 is False：None 意为未表态，交由会话决定，不可在此就套上跳板
        if trusted is False:
            # 使用 mm.teahouse.team 的跳板服务，用于隐藏原始链接
            mm_url = "https://mm.teahouse.team/index.html?source=akaribot&rot13=%s"
            rot13 = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM",
            )
            url = mm_url % parse.quote(parse.unquote(url).translate(rot13))

        if md_format:
            url = f"[{md_format_name if md_format_name else url}]({url})"

        return deepcopy(
            cls(
                original_url=original_url,
                url=url,
                trusted=trusted,
                applied_md_format=md_format,
                md_format_name=md_format_name,
            )
        )

    def kecode(self):
        """转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        encoded = parse.quote(self.original_url, safe="")
        if self.trusted is None:
            return f"[KE:url,text={encoded}]"
        return f"[KE:url,text={encoded},trusted={'1' if self.trusted else '0'}]"

    def __str__(self):
        """返回 URL 地址或转换后的链接"""
        return self.url


@define
class FormattedTimeElement(BaseElement):
    """格式化时间元素 - 用于在消息中包含格式化的时间信息。"""

    timestamp: float
    date: bool = True
    simple: bool = False
    time: bool = True
    seconds: bool = True
    timezone: bool = True

    def to_str(self, session_info: SessionInfo | None = None):
        """将时间元素转换为格式化的字符串。

        :param session_info: 会话信息，包含地区设置和时区信息
        :return: 格式化后的时间字符串
        """
        ftime_template = []
        if session_info:
            dt = datetime.fromtimestamp(self.timestamp, UTC) + session_info.timezone_offset

            if self.date:
                if self.simple:
                    ftime_template.append(session_info.locale.t("time.date.simple.format"))
                else:
                    ftime_template.append(session_info.locale.t("time.date.format"))

            if self.time:
                if self.seconds:
                    ftime_template.append(session_info.locale.t("time.time.format"))
                else:
                    ftime_template.append(session_info.locale.t("time.time.nosec.format"))

            if self.timezone:
                if session_info._tz_offset == "+0":
                    ftime_template.append("(UTC)")
                else:
                    ftime_template.append(f"(UTC{session_info._tz_offset})")

            return safe_strftime(dt, " ".join(ftime_template))

        if self.date:
            if self.simple:
                ftime_template.append("%Y-%m-%d")
            else:
                ftime_template.append("%B %d, %Y")

        if self.time:
            if self.seconds:
                ftime_template.append("%H:%M:%S")
            else:
                ftime_template.append("%H:%M")

        if self.timezone:
            tz_template = "(UTC)"
            offset = datetime.now().astimezone().utcoffset()
            if offset:
                total_min = int(offset.total_seconds() // 60)
                sign = "+" if total_min >= 0 else "-"
                abs_min = abs(total_min)
                hours = abs_min // 60
                mins = abs_min % 60

                if mins == 0:
                    tz_template = f"(UTC{sign}{hours})" if hours != 0 else "(UTC)"
                else:
                    tz_template = f"(UTC{sign}{hours}:{mins:02d})"

            ftime_template.append(tz_template)

        return safe_strftime(datetime.fromtimestamp(self.timestamp), " ".join(ftime_template))

    def kecode(self, session_info: SessionInfo | None = None):
        """转换为 KE 码格式。

        :param session_info: 会话信息，用于本地化转换
        :return: KE 码格式的字符串
        """
        return f"[KE:plain,text={parse.quote(self.to_str(session_info), safe='')}]"

    def __str__(self):
        """返回默认格式的时间字符串"""
        return self.to_str()

    @classmethod
    def assign(
        cls,
        timestamp: float,
        date: bool = True,
        simple: bool = False,
        time: bool = True,
        seconds: bool = True,
        timezone: bool = True,
    ):
        """
        创建格式化时间元素的工厂方法。

        :param timestamp: UTC 时间戳
        :param date: 是否显示日期（默认为 True）
        :param simple: 是否以简单格式显示日期（默认为 False）
        :param time: 是否显示时间（默认为 True）
        :param seconds: 是否显示秒（默认为 True）
        :param timezone: 是否显示时区（默认为 True）
        :return: FormattedTimeElement 实例
        """
        return deepcopy(
            cls(
                timestamp=timestamp,
                date=date,
                simple=simple,
                time=time,
                seconds=seconds,
                timezone=timezone,
            )
        )


@define
class I18NContextElement(BaseElement):
    """带有多语言的消息元素。"""

    key: str
    kwargs: dict[str, Any]
    fallback: bool = True
    locale_failed_prompt: bool = True
    disable_joke: bool = False

    @classmethod
    def assign(
        cls,
        key: str,
        fallback: bool = True,
        locale_failed_prompt: bool = True,
        disable_joke: bool = False,
        **kwargs: Any,
    ):
        """
        创建多语言消息元素的工厂方法。

        :param key: 多语言的键名（如 "message.list" -> "消息列表"）
        :param fallback: 是否启用 fallback。（默认为 True）
        :param locale_failed_prompt: 是否添加本地化失败提示。（默认为 True）
        :param disable_joke: 是否禁用玩笑功能（默认为 False）
        :param kwargs: 多语言字符串中的变量（如 name="Alice", count=5）
        :return: I18NContextElement 实例
        """
        return deepcopy(
            cls(
                key=key,
                fallback=fallback,
                locale_failed_prompt=locale_failed_prompt,
                disable_joke=disable_joke,
                kwargs=kwargs,
            )
        )

    def _get_combined_params(self) -> dict[str, Any]:
        full_params = {}
        if not self.fallback:
            full_params["fallback"] = 0
        if not self.locale_failed_prompt:
            full_params["locale_failed_prompt"] = 0
        if self.disable_joke:
            full_params["disable_joke"] = 1
        if self.kwargs:
            full_params |= self.kwargs.copy()

        return full_params

    def kecode(self):
        """转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        combined = self._get_combined_params()
        if combined:
            params_str = ",".join(f"{k}={v}" for k, v in combined.items())
            return f"[KE:i18n,i18nkey={self.key},{params_str}]"
        return f"[KE:i18n,i18nkey={self.key}]"

    def __str__(self):
        """
        返回多语言标记表示。

        :return:多语言标记格式的字符串表示
        """
        if self.kwargs:
            params = ",".join(f"{k}={v}" for k, v in self.kwargs.items())
            return f"{{I18N:{self.key},{params}}}"
        return f"{{I18N:{self.key}}}"


@define
class ImageElement(BaseElement):
    """图片消息元素。"""

    path: str
    headers: dict[str, Any] | None = None
    need_get: bool = False
    cached_b64: str | None = None
    max_h: int | None = None
    allow_split: bool = True

    @classmethod
    def assign(
        cls,
        path: str | Path | PILImage.Image,
        headers: dict[str, Any] | None = None,
        max_h: int | None = None,
        allow_split: bool = True,
    ):
        """创建图片元素的工厂方法。

        :param path: 图片来源，可以是：
                    - 本地文件路径（str 或 Path）
                    - URL 地址（以 `http://` 或 `https://` 开头）
                    - Base64 编码数据（以 base64 开头）
                    - PIL Image 对象
        :param headers: 获取网络图片时的请求头（如用户代理、认证信息等）
        :param max_h: QQBot Markdown 图片的最大显示宽度（像素）
        :param allow_split: 平台发送时是否允许按高度拆分图片
        :return: ImageElement 实例
        """
        need_get = False
        if isinstance(path, PILImage.Image):
            image_format = (path.format or "PNG").upper()
            extension = {
                "JPEG": "jpg",
                "JPEG2000": "jp2",
            }.get(image_format, image_format.lower())
            save = random_cache_path(extension)
            path.save(save, format=image_format)
            path = str(save)
        elif isinstance(path, Path):
            path = str(path)

        if re.match("^https?://.*", path):
            need_get = True
        elif "base64" in path:
            extension = None
            if path.startswith("base64://"):
                img_data = base64.b64decode(path[len("base64://") :])

            elif path.startswith("data:"):
                metadata, encoded_img = path.split(",", 1)
                img_data = base64.b64decode(encoded_img)
                mime_type = metadata[len("data:") :].split(";", 1)[0]
                extension = (mimetypes.guess_extension(mime_type, strict=False) or "").lstrip(".")
            else:
                Logger.error("Cannot match format for Base64 image data.")
                img_data = None

            if img_data:
                detected = filetype.match(img_data)
                extension = detected.extension if detected else extension or "png"
                save = random_cache_path(extension)
                with open(save, "wb") as img_file:
                    img_file.write(img_data)
                path = save

        normalized_max_h = max(1, int(max_h)) if max_h is not None else None
        return deepcopy(
            cls(
                path=str(path),
                headers=headers,
                need_get=need_get,
                max_h=normalized_max_h,
                allow_split=bool(allow_split),
            )
        )

    async def get(self) -> str:
        """获取图片的实际路径。

        :return: 本地文件路径字符串
        :raise FileNotFoundError: 本地图片文件不存在。
        """
        if self.need_get:
            return str(await self.get_image())
        # 本地路径须确认文件存在，否则调用方应跳过该元素
        if not Path(self.path).is_file():
            raise FileNotFoundError(f"Image file not found: {self.path}")
        # 返回本地路径
        return self.path

    @retry(stop=stop_after_attempt(3))
    async def get_image(self) -> Path:
        """从网络下载图片。

        :return: 本地缓存文件的 Path 对象
        :raise ValueError: 响应状态码异常或下载到的内容并非图片。
        """
        url = self.path
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=20.0, headers=self.headers)
            resp.raise_for_status()
            raw = resp.content
            # 自动识别图片格式，识别失败的响应体（如 JS、HTML）不应写入缓存
            kind = filetype.match(raw)
            if not kind:
                raise ValueError(f"Content fetched from {url} is not a recognized image file.")
            img_path = random_cache_path(kind.extension)
            with open(img_path, "wb+") as image_cache:
                image_cache.write(raw)
            return img_path

    async def get_base64(self, mime: bool = False) -> str:
        """获取图片的 Base64 编码字符串。

        :param mime: 是否包含 MIME 类型前缀（如 data:image/png;base64,...）
        :return: Base64 编码的字符串
        """
        file = await self.get()

        with open(file, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("UTF-8")
        self.cached_b64 = img_b64
        # Logger.debug(f"ImageElement: Cached base64 for {file}")

        if mime:
            mime_type, _ = mimetypes.guess_type(file)
            if not mime_type:
                mime_type = "application/octet-stream"
            self.cached_b64 = f"data:{mime_type};base64,{img_b64}"
            return self.cached_b64
        return img_b64

    async def add_random_noise(self) -> "ImageElement":
        """为图片添加随机噪点。

        :return: 新的 ImageElement 实例
        """
        image = PILImage.open(await self.get())
        image = image.convert("RGBA")

        noise_image = PILImage.new("RGBA", (50, 50))
        for i in range(50):
            for j in range(50):
                noise_image.putpixel((i, j), (i, j, i, random.randint(0, 1)))

        image.alpha_composite(noise_image)

        save = f"{random_cache_path()}.png"
        image.save(save)
        image.close()
        return ImageElement.assign(save, max_h=self.max_h, allow_split=self.allow_split)

    def kecode(self):
        """
        转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        params = [f"path={self.path}"]
        if self.headers:
            headers_b64 = base64.b64encode(orjson.dumps(self.headers)).decode("utf-8")
            params.append(f"headers={headers_b64}")
        if self.max_h is not None:
            params.append(f"max_h={self.max_h}")
        if not self.allow_split:
            params.append("allow_split=0")
        return f"[KE:image,{','.join(params)}]"

    async def to_PIL_image(self) -> PILImage.Image:
        """将图片元素转换为 PIL Image 对象。

        :return: PIL Image 对象
        """
        return PILImage.open(await self.get())

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()

    async def get_wh(self):
        """获取图片的宽度和高度"""
        image = await self.to_PIL_image()
        width, height = image.size
        image.close()
        return width, height


@define
class AudioElement(BaseElement):
    """语音消息元素。"""

    path: str

    @classmethod
    def assign(cls, path: str | Path):
        """
        创建语音元素的工厂方法。

        :param path: 语音文件的本地路径（str 或 Path 对象）
        :return: AudioElement 实例
        """
        return deepcopy(cls(str(path)))

    def kecode(self):
        """转换为 KE 码格式"""
        return f"[KE:audio,path={self.path}]"

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()


@define
class VideoElement(BaseElement):
    """视频消息元素。"""

    path: str

    @classmethod
    def assign(cls, path: str | Path):
        """
        创建语音元素的工厂方法。

        :param path: 语音文件的本地路径（str 或 Path 对象）
        :return: VideoElement 实例
        """
        return deepcopy(cls(str(path)))

    def kecode(self):
        """转换为 KE 码格式"""
        return f"[KE:video,path={self.path}]"

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()


@define
class MentionElement(BaseElement):
    """提及元素 - 用于在消息中提及（@）其他用户。"""

    client: str
    id: str

    @classmethod
    def assign(cls, user_id: str):
        """
        创建提及元素的工厂方法。

        :param user_id: 用户标识符，格式为 "client|userid"
                       如 "QQ|123456789" 表示 QQ 平台的用户
        :return: MentionElement 实例
        """
        return deepcopy(cls(client=user_id.split("|")[0], id=user_id.split("|")[-1]))

    def kecode(self):
        """转换为 KE 码格式"""
        return f"[KE:mention,userid={self.client}|{self.id}]"

    def __str__(self):
        """返回 AT 码格式"""
        return f"<AT:{self.client}|{self.id}>"


def _as_inner_element(value: str | PlainElement | I18NContextElement) -> PlainElement | I18NContextElement:
    if isinstance(value, str):
        return PlainElement.assign(value)
    return value


def _resolve_inner_text(
    element: PlainElement | I18NContextElement | None,
    session_info: SessionInfo | None,
) -> str:
    if element is None:
        return ""
    if isinstance(element, I18NContextElement):
        if session_info:
            return session_info.locale.t(
                element.key,
                element.fallback,
                element.locale_failed_prompt,
                **element.kwargs,
            )
        return str(element)
    if isinstance(element, PlainElement):
        if session_info:
            return session_info.locale.t_str(element.text)
        return element.text
    return str(element)


@define
class ActionTextElement(BaseElement):
    """指令操作元素 - 用于在消息中嵌入可点击的命令入口。"""

    text: PlainElement | I18NContextElement
    show: PlainElement | I18NContextElement | None = None
    reference: bool = False
    show_on_fallback: bool = True
    quote_on_fallback: bool = False

    @classmethod
    def assign(
        cls,
        text: str | PlainElement | I18NContextElement,
        show: str | PlainElement | I18NContextElement | None = None,
        reference: bool = False,
        show_on_fallback: bool = True,
        quote_on_fallback: bool = False,
    ):
        """
        创建指令操作元素的工厂方法。

        :param text: 点击后插入输入框的文本
        :param show: 消息内展示的文本（默认为 None，由平台取 text）
        :param reference: 插入输入框时是否携带引用回复（默认为 False）
        :param show_on_fallback: 降级为纯文本时是否带上 show（默认为 True）
        :param quote_on_fallback: 降级为纯文本时是否为文案加上引号（默认为 False）
        :return: ActionTextElement 实例
        """
        return deepcopy(
            cls(
                text=_as_inner_element(text),
                show=_as_inner_element(show) if show is not None else None,
                reference=bool(reference),
                show_on_fallback=bool(show_on_fallback),
                quote_on_fallback=bool(quote_on_fallback),
            )
        )

    def resolve(self, session_info: SessionInfo | None = None) -> "ActionTextElement":
        """将内层元素解析为纯文本，返回新实例。

        :param session_info: 会话信息，用于多语言翻译
        :return: 内层全为纯文本元素的新实例
        """
        return ActionTextElement(
            text=PlainElement.assign(_resolve_inner_text(self.text, session_info)),
            show=(PlainElement.assign(_resolve_inner_text(self.show, session_info)) if self.show is not None else None),
            reference=self.reference,
            show_on_fallback=self.show_on_fallback,
            quote_on_fallback=self.quote_on_fallback,
        )

    def to_plain(self, session_info: SessionInfo | None = None) -> PlainElement:
        """降级为纯文本元素，用于不支持指令操作的平台。

        :param session_info: 会话信息，用于多语言翻译与括号样式
        :return: 降级后的纯文本元素
        """
        resolved = self.resolve(session_info)
        text = resolved.text.text
        if self.quote_on_fallback:
            text = session_info.locale.t("message.quotes", msg=text) if session_info else f'"{text}"'
        show = resolved.show.text if (resolved.show and self.show_on_fallback) else ""
        if not show:
            return PlainElement.assign(text)
        if session_info:
            return PlainElement.assign(f"{show}{session_info.locale.t('message.brackets', msg=text)}")
        return PlainElement.assign(f"{show} ({text})")

    def kecode(self):
        """转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        resolved = self.resolve()
        params = [f"text={parse.quote(resolved.text.text, safe='')}"]
        if resolved.show is not None:
            params.append(f"show={parse.quote(resolved.show.text, safe='')}")
        params.append(f"reference={1 if self.reference else 0}")
        # 仅在非默认时写出，避免既有 KE 码平白变长
        if not self.show_on_fallback:
            params.append("show_on_fallback=0")
        if self.quote_on_fallback:
            params.append("quote_on_fallback=1")
        return f"[KE:action_text,{','.join(params)}]"

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()


_BUTTON_REPLY_PATTERN = re.compile(r"<q:(.*?)>(.*)", re.DOTALL)
_BUTTON_LIMIT_PATTERN = re.compile(r"<l:(\d+)>(.*)", re.DOTALL)
_BUTTON_PUBLIC_MARKER = "<a:1>"


class ButtonPermission(str, Enum):
    """按钮点击权限。默认仅允许发送按钮的用户点击。"""

    OWNER = "owner"
    ALL = "all"
    EVERYONE = "all"

    @classmethod
    def normalize(cls, value: "ButtonPermission | str | bool | None") -> "ButtonPermission":
        """把公开 API 接受的权限写法归一化为枚举值。"""
        if isinstance(value, cls):
            return value
        if value is True:
            return cls.ALL
        if value is False or value is None:
            return cls.OWNER
        normalized = str(value).strip().lower()
        if normalized in {"all", "everyone", "public"}:
            return cls.ALL
        if normalized in {"owner", "sender", "user", "private"}:
            return cls.OWNER
        raise ValueError(f"Unknown button permission: {value!r}")


def normalize_button_click_limit(value: int | None) -> int | None:
    """归一化按钮点击次数；``None`` / ``0`` 表示不限次数。"""
    if value is None or value == 0:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Button click_limit must be a non-negative integer or None.")
    return value


@define(frozen=True)
class ButtonPayload:
    """按钮点击所携带的语义数据。"""

    value: str
    reply_id: str | None = None
    permission: ButtonPermission = ButtonPermission.OWNER
    click_limit: int | None = 1

    @classmethod
    def parse(
        cls,
        data: str,
        reply_id: str | None = None,
        permission: ButtonPermission | str | bool | None = ButtonPermission.OWNER,
        click_limit: int | None = 1,
    ):
        """从平台数据或旧版 ``<q:reply_id>value`` 编码恢复语义字段。"""
        data = str(data)
        normalized_permission = ButtonPermission.normalize(permission)
        if data.startswith(_BUTTON_PUBLIC_MARKER):
            normalized_permission = ButtonPermission.ALL
            data = data[len(_BUTTON_PUBLIC_MARKER) :]
        encoded_click_limit = click_limit
        if match := _BUTTON_LIMIT_PATTERN.fullmatch(data):
            encoded_click_limit = int(match.group(1))
            data = match.group(2)
        legacy_reply_id = None
        if match := _BUTTON_REPLY_PATTERN.fullmatch(data):
            legacy_reply_id = match.group(1) or None
            data = match.group(2)
        return cls(
            value=data,
            reply_id=str(reply_id) if reply_id is not None else legacy_reply_id,
            permission=normalized_permission,
            click_limit=normalize_button_click_limit(encoded_click_limit),
        )

    def to_data(self) -> str:
        """编码为只支持单个字符串字段的平台按钮数据。"""
        public_marker = _BUTTON_PUBLIC_MARKER if self.permission is ButtonPermission.ALL else ""
        reply_marker = "" if self.reply_id is None else f"<q:{self.reply_id}>"
        limit_marker = "" if self.click_limit == 1 else f"<l:{self.click_limit or 0}>"
        return f"{public_marker}{limit_marker}{reply_marker}{self.value}"


@define
class ButtonElement(BaseElement):
    """单个消息按钮元素。"""

    show: str
    value: str
    reply_id: str | None = None
    permission: ButtonPermission = ButtonPermission.OWNER
    click_limit: int | None = 1

    @classmethod
    def assign(
        cls,
        show: str,
        value: str,
        reply_id: str | None = None,
        permission: ButtonPermission | str | bool | None = ButtonPermission.OWNER,
        click_limit: int | None = 1,
    ):
        """创建单个按钮，show 为展示文本，value 为点击数据，permission 可设为 ``"all"``。"""
        payload = ButtonPayload.parse(value, reply_id, permission, click_limit)
        return deepcopy(
            cls(
                show=str(show),
                value=payload.value,
                reply_id=payload.reply_id,
                permission=payload.permission,
                click_limit=payload.click_limit,
            )
        )

    @property
    def payload(self) -> ButtonPayload:
        """返回按钮点击数据；同时兼容反序列化得到的旧版内嵌编码。"""
        return ButtonPayload.parse(self.value, self.reply_id, self.permission, self.click_limit)

    def kecode(self):
        """转换为 KE 码格式。"""
        show = parse.quote(self.show, safe="")
        value = parse.quote(self.value, safe="")
        params = [f"show={show}", f"value={value}"]
        if self.reply_id is not None:
            params.append(f"reply_id={parse.quote(self.reply_id, safe='')}")
        if ButtonPermission.normalize(self.permission) is ButtonPermission.ALL:
            params.append("permission=all")
        if self.click_limit != 1:
            params.append(f"click_limit={self.click_limit or 0}")
        return f"[KE:button,{','.join(params)}]"

    def __str__(self):
        """返回 KE 码格式。"""
        return self.kecode()


@define
class ButtonRows:
    """消息按钮的一行。"""

    buttons: list[ButtonElement]

    @classmethod
    def assign(cls, buttons: list[ButtonElement] | None = None):
        """使用单个按钮元素组成一行。"""
        normalized = []
        for button in buttons or []:
            if not isinstance(button, ButtonElement):
                raise TypeError("ButtonRows only accepts Button elements.")
            normalized.append(button)
        return deepcopy(cls(buttons=normalized))


@define
class ButtonFrameElement(BaseElement):
    """消息底部的完整按钮区域。"""

    rows: list[ButtonRows]

    @classmethod
    def assign(cls, rows: list[ButtonRows] | None = None):
        """使用按钮行组成完整按钮区域。"""
        normalized = []
        for row in rows or []:
            if not isinstance(row, ButtonRows):
                raise TypeError("ButtonFrame only accepts ButtonRows elements.")
            if row.buttons:
                normalized.append(row)
        return deepcopy(cls(rows=normalized))

    def kecode(self):
        """转换为 KE 码格式。"""
        rows = [
            [
                {
                    "show": button.show,
                    "value": button.value,
                    **({"reply_id": button.reply_id} if button.reply_id is not None else {}),
                    **(
                        {"permission": ButtonPermission.ALL.value}
                        if ButtonPermission.normalize(button.permission) is ButtonPermission.ALL
                        else {}
                    ),
                    **({"click_limit": button.click_limit or 0} if button.click_limit != 1 else {}),
                }
                for button in row.buttons
            ]
            for row in self.rows
        ]
        data = parse.quote(orjson.dumps(rows).decode("utf-8"), safe="")
        return f"[KE:button_frame,data={data}]"

    def __str__(self):
        """返回 KE 码格式。"""
        return self.kecode()


@define
class EmbedFieldElement(BaseElement):
    """Embed 字段元素 - 用于构建嵌入式消息的字段。"""

    name: str
    value: str
    inline: bool = False

    @classmethod
    def assign(cls, name: str, value: str, inline: bool = False):
        """
        创建 Embed 字段的工厂方法。

        :param name: 字段名称/标题
        :param value: 字段值/内容
        :param inline: 是否内联显示，默认为 False
                      True 表示多个字段可在同一行显示
        :return: EmbedFieldElement 实例
        """
        return deepcopy(cls(name=name, value=value, inline=inline))

    def kecode(self):
        """... KE 码格式未实现 ..."""

    def __str__(self):
        """返回字符串表示"""
        return f"[EmbedField:{self.name},{self.value},{self.inline}]"


@define
class EmbedElement(BaseElement):
    """Embed 消息元素 - 用于创建富文本嵌入式消息。"""

    title: str | None = None
    description: str | None = None
    url: str | None = None
    timestamp: float = datetime.now().timestamp()
    color: int = 0x0091FF
    image: ImageElement | None = None
    thumbnail: ImageElement | None = None
    author: str | None = None
    footer: str | None = None
    fields: list[EmbedFieldElement] | None = None

    @classmethod
    def assign(
        cls,
        title: str | None = None,
        description: str | None = None,
        url: str | None = None,
        timestamp: float = datetime.now().timestamp(),
        color: int = 0x0091FF,
        image: ImageElement | None = None,
        thumbnail: ImageElement | None = None,
        author: str | None = None,
        footer: str | None = None,
        fields: list[EmbedFieldElement] | None = None,
    ):
        """
        创建 Embed 消息的工厂方法。

        :param title: 标题
        :param description: 描述
        :param url: 跳转链接
        :param timestamp: 时间戳（默认为当前时间）
        :param color: 颜色值（十六进制，默认为 0x0091FF）
        :param image: 主图片对象
        :param thumbnail: 缩略图对象
        :param author: 作者名称
        :param footer: 页脚文本
        :param fields: 字段列表
        :return: EmbedElement 实例
        """
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

    def to_message_chain(self, session_info: SessionInfo | None = None):
        """将 Embed 转换为消息链。

        :param session_info: 会话信息，用于多语言翻译和格式化
        :return: 消息元素列表
        """
        text_lst = []

        if self.title:
            text_lst.append(self.title)
        if self.description:
            text_lst.append(self.description)
        if self.url:
            text_lst.append(self.url)

        if self.fields:
            for f in self.fields if isinstance(self.fields, list) else [self.fields] if self.fields else []:
                if session_info:
                    text_lst.append(
                        f"{session_info.locale.t_str(f.name)}{session_info.locale.t('message.colon')}{
                            session_info.locale.t_str(f.value)
                        }"
                    )
                else:
                    text_lst.append(f"{f.name}: {f.value}")

        if self.author:
            if session_info:
                text_lst.append(
                    f"{session_info.locale.t('message.embed.author')}{session_info.locale.t_str(self.author)}"
                )
            else:
                text_lst.append(f"Author: {self.author}")

        if self.footer:
            if session_info:
                text_lst.append(session_info.locale.t_str(self.footer))
            else:
                text_lst.append(self.footer)

        message_chain = []
        if text_lst:
            message_chain.append(PlainElement.assign("\n".join(text_lst)))
        if self.image:
            message_chain.append(self.image)

        return message_chain

    def kecode(self):
        """... KE 码格式未实现 ..."""

    def __str__(self):
        """返回消息链的字符串表示"""
        return str(self.to_message_chain())


@define
class RawElement(BaseElement):
    """原始元素 - 用于包含未处理的原始数据。"""

    value: str

    @classmethod
    def assign(cls, value: str):
        """
        创建原始元素的工厂方法。

        :param value: 原始数据值
        :return: RawElement 实例
        """
        return deepcopy(cls(value=value))

    def kecode(self):
        """... KE 码格式未实现 ..."""

    def __str__(self):
        """返回原始值"""
        return self.value


__all__ = [
    "BaseElement",
    "PlainElement",
    "MarkdownElement",
    "markdown_to_plain_text",
    "URLElement",
    "FormattedTimeElement",
    "I18NContextElement",
    "ImageElement",
    "AudioElement",
    "VideoElement",
    "EmbedFieldElement",
    "EmbedElement",
    "MentionElement",
    "ActionTextElement",
    "ButtonPermission",
    "normalize_button_click_limit",
    "ButtonPayload",
    "ButtonElement",
    "ButtonRows",
    "ButtonFrameElement",
    "RawElement",
]
