"""
消息元素模块 - 定义各种类型的消息元素。

该模块定义了所有支持的消息元素类型，如纯文本、URL、图片、语音、嵌入式内容等。
每个元素都代表消息链中的一个组成部分。
"""

from __future__ import annotations

import base64
import mimetypes
import random
import re
from copy import deepcopy
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib import parse

import httpx
import orjson
from PIL import Image as PILImage
from attrs import define
from filetype import filetype
from japanera import EraDate
from tenacity import retry, stop_after_attempt

from core.utils.cache import random_cache_path

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo


class BaseElement:
    """
    消息元素基类。

    所有消息元素的基类，定义了元素应该实现的接口。

    消息系统中的元素必须继承此类并实现以下方法：
    - kecode()：将元素转换为 KE 码格式
    - __str__()：将元素转换为字符串表示

    KE 码格式说明：
    KE 码是 AkariBot 的消息元素文本化的格式，用于在不便于使用标准的元素类的情况下使用。
    在机器人发出消息的最后阶段，KE 码会被解析器解析成对应的消息元素对象。
    格式为 `[KE:type,param1=value1,param2=value2]`，其中：
    - type：元素类型（plain、image、voice、mention 等）
    - param*：元素特定的参数

    示例：
        纯文本：`[KE:plain,text=Hello]`
        图片：`[KE:image,path=/path/to/image.png]`
        提及：`[KE:mention,userid=QQ|123456789]`
    """

    @classmethod
    def __name__(cls):
        """
        获取元素类名。

        :return: 类的名称字符串
        """
        return cls.__name__

    def kecode(self):
        """
        转换为 KE 码格式（AkariBot 特定的消息格式）。

        KE 码是 AkariBot 的消息元素文本化的格式，用于在不便于使用标准的元素类的情况下使用。
        在机器人发出消息的最后阶段，KE 码会被解析器解析成对应的消息元素对象。

        :return: KE 码格式的字符串
        :raises NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    def __str__(self):
        """
        转换为字符串表示。

        该方法返回元素的可读字符串表示。

        :return: 字符串表示
        :raises NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError


@define
class PlainElement(BaseElement):
    """
    纯文本元素 - 用于表示消息中的纯文本内容。

    该类用于创建和处理消息中的文本部分。

    属性：
        text: 文本内容，可以包含任何字符串
        disable_joke: 是否禁用玩笑功能，True 表示此文本内容不应被玩笑影响

    示例：
    ```
        > plain = PlainElement.assign("Hello, World!")
        > str(plain)
        'Hello, World!'
    ```
    """

    text: str
    disable_joke: bool = False

    @classmethod
    def assign(cls, *texts: Any, disable_joke: bool = False):
        """
        创建纯文本元素的工厂方法。

        该方法是创建 PlainElement 的推荐方式，支持多个参数自动拼接，
        并进行深拷贝以确保数据安全。

        :param texts: 文本内容（支持多个参数），每个参数会被转换为字符串并拼接
        :param disable_joke: 是否禁用玩笑功能（默认为 False）
        :return: PlainElement 实例
        """
        # 将所有参数转换为字符串并用空字符连接（保留原始格式）
        text = "".join([str(x) for x in texts])
        disable_joke = bool(disable_joke)
        return deepcopy(cls(text=text, disable_joke=disable_joke))

    def kecode(self):
        """
        转换为 KE 码格式。

        纯文本在 KE 码中用 `[KE:plain,text=...]` 表示。

        :return: KE 码格式的字符串
        """
        return f"[KE:plain,text={self.text}]"

    def __str__(self):
        """返回文本内容"""
        return self.text


@define
class URLElement(BaseElement):
    """
    URL 链接元素 - 用于在消息中包含链接。

    该类用于处理消息中的超链接，支持多种功能：
    1. 链接跳板（mm_url）：通过 ROT13 转换隐藏原始链接
    2. Markdown 格式：支持 [名称](URL) 的 Markdown 语法

    属性：
        url: URL 地址或已转换的链接
        applied_mm: 是否应用了链接跳板（None 表示自动选择）
        applied_md_format: 是否使用 Markdown 格式
        md_format_name: Markdown 格式的链接显示名称

    示例：
    ```
        > url = URLElement.assign("https://example.com")
        > str(url)
        'https://example.com'
    ```
    """

    url: str
    applied_mm: bool | None = None
    applied_md_format: bool = False
    md_format_name: str | None = None

    @classmethod
    def assign(cls, url: str, use_mm: bool | None = None, md_format: bool = False, md_format_name: str | None = None):
        """
        创建 URL 元素的工厂方法。

        支持链接跳板和 Markdown 格式两种转换。

        :param url: URL 地址
        :param use_mm: 是否使用链接跳板，覆盖全局设置
                      None 表示根据客户端情况自动选择（默认）
                      True 表示强制使用跳板
                      False 表示不使用跳板
        :param md_format: 是否使用 Markdown 格式（默认为 False）
                         True 表示转换为 [名称](URL) 格式
        :param md_format_name: Markdown 格式的链接名称（默认为 None，使用 URL 本身）
        :return: URLElement 实例
        """
        # ========== 步骤 1: 应用链接跳板（如果需要）==========
        if use_mm:
            # 使用 mm.teahouse.team 的跳板服务，用于隐藏原始链接
            mm_url = "https://mm.teahouse.team/?source=akaribot&rot13=%s"
            # 创建 ROT13 转换表（字母表循环移位 13 位）
            rot13 = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM",
            )
            # 对 URL 进行 ROT13 转换和 URL 编码，然后使用跳板 URL
            url = mm_url % parse.quote(parse.unquote(url).translate(rot13))

        # ========== 步骤 2: 应用 Markdown 格式（如果需要）==========
        if md_format:
            # 将 URL 转换为 Markdown 链接格式 [名称](URL)
            url = f"[{md_format_name if md_format_name else url}]({url})"

        return deepcopy(cls(url=url, applied_mm=use_mm, applied_md_format=md_format, md_format_name=md_format_name))

    def kecode(self):
        """
        转换为 KE 码格式。

        URL 在 KE 码中以纯文本形式表示，系统会自动识别和处理链接。

        :return: KE 码格式的字符串
        """
        return f"[KE:plain,text={self.url}]"

    def __str__(self):
        """返回 URL 地址或转换后的链接"""
        return self.url


@define
class FormattedTimeElement(BaseElement):
    """
    格式化时间元素 - 用于在消息中包含格式化的时间信息。

    该类支持多种时间格式化选项，包括日期、时间、秒、时区等。
    可根据会话的地区设置进行本地化格式化，支持日本年号显示。

    属性：
        timestamp: UTC 时间戳（浮点数）
        date: 是否显示日期（默认为 True）
        iso: 是否使用 ISO 格式显示日期（默认为 False）
        time: 是否显示时间（默认为 True）
        seconds: 是否显示秒（默认为 True）
        timezone: 是否显示时区（默认为 True）

    示例：
    ```
        > elem = FormattedTimeElement.assign(1234567890, date=True, time=True)
        > str(elem)
        'February 13, 2009 23:31:30 (UTC)'
    ```
    """

    timestamp: float
    date: bool = True
    iso: bool = False
    time: bool = True
    seconds: bool = True
    timezone: bool = True

    def to_str(self, session_info: SessionInfo | None = None):
        """
        将时间元素转换为格式化的字符串。

        根据 session_info 进行本地化处理，包括时区转换、地区特定的日期格式等。

        :param session_info: 会话信息，包含地区设置和时区信息
        :return: 格式化后的时间字符串
        """
        ftime_template = []
        if session_info:
            # ========== 使用会话信息进行本地化格式化 ==========
            # 根据会话的时区转换时间
            dt = datetime.fromtimestamp(self.timestamp, UTC) + session_info.timezone_offset

            if self.date:
                # ========== 日期格式化 ==========
                if self.iso:
                    # ISO 格式：YYYY-MM-DD
                    ftime_template.append(session_info.locale.t("time.date.iso.format"))
                elif session_info.locale.locale == "ja_jp":
                    # 日本格式：支持年号显示（如 令和 5 年）
                    era_date = EraDate.from_date(dt).strftime(session_info.locale.t("time.date.format"))
                    ftime_template.append(era_date)
                else:
                    # 其他地区的日期格式
                    ftime_template.append(session_info.locale.t("time.date.format"))

            if self.time:
                # ========== 时间格式化 ==========
                if self.seconds:
                    # 显示秒：HH:MM:SS
                    ftime_template.append(session_info.locale.t("time.time.format"))
                else:
                    # 不显示秒：HH:MM
                    ftime_template.append(session_info.locale.t("time.time.nosec.format"))

            if self.timezone:
                # ========== 时区格式化 ==========
                if session_info._tz_offset == "+0":
                    # UTC 时区
                    ftime_template.append("(UTC)")
                else:
                    # 其他时区，显示偏移量
                    ftime_template.append(f"(UTC{session_info._tz_offset})")

            return dt.strftime(" ".join(ftime_template))

        # ========== 不使用会话信息的默认格式化 ==========
        if self.date:
            if self.iso:
                # ISO 格式：YYYY-MM-DD
                ftime_template.append("%Y-%m-%d")
            else:
                # 英文格式：Month DD, YYYY
                ftime_template.append("%B %d, %Y")

        if self.time:
            if self.seconds:
                # 显示秒：HH:MM:SS
                ftime_template.append("%H:%M:%S")
            else:
                # 不显示秒：HH:MM
                ftime_template.append("%H:%M")

        if self.timezone:
            # ========== 计算本地时区偏移量 ==========
            tz_template = "(UTC)"
            offset = datetime.now().astimezone().utcoffset()
            if offset:
                # 计算时区偏移（分钟）
                total_min = int(offset.total_seconds() // 60)
                sign = "+" if total_min >= 0 else "-"
                abs_min = abs(total_min)
                hours = abs_min // 60
                mins = abs_min % 60

                # 格式化时区字符串
                if mins == 0:
                    tz_template = f"(UTC{sign}{hours})" if hours != 0 else "(UTC)"
                else:
                    tz_template = f"(UTC{sign}{hours}:{mins:02d})"

            ftime_template.append(tz_template)

        return datetime.fromtimestamp(self.timestamp).strftime(" ".join(ftime_template))

    def kecode(self, session_info: SessionInfo | None = None):
        """
        转换为 KE 码格式。

        :param session_info: 会话信息，用于本地化转换
        :return: KE 码格式的字符串
        """
        return f"[KE:plain,text={self.to_str(session_info)}]"

    def __str__(self):
        """返回默认格式的时间字符串"""
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
        创建格式化时间元素的工厂方法。

        :param timestamp: UTC 时间戳
        :param date: 是否显示日期（默认为 True）
        :param iso: 是否以 ISO 格式显示日期（默认为 False）
        :param time: 是否显示时间（默认为 True）
        :param seconds: 是否显示秒（默认为 True）
        :param timezone: 是否显示时区（默认为 True）
        :return: FormattedTimeElement 实例
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
class I18NContextElement(BaseElement):
    """
    带有多语言的消息元素。

    该类用于创建包含多语言支持的消息元素。通过指定多语言键名和参数，
    系统会在实际发送消息时根据接收者的地区设置自动翻译内容。

    属性：
        key: 多语言字典中的键名，格式如 "message.hello"、"error.permission.denied" 等
        disable_joke: 是否禁用玩笑功能，True 表示此文本内容不应被玩笑影响
        kwargs: 多语言字符串中的变量字典，如 `{"user": "Alice", "count": 10}`

    示例：
    ```
        > elem = I18NContextElement.assign("message.hello", user="Alice")
        > str(elem)
        '{I18N:message.hello,user=Alice}'
    ```
    """

    key: str
    disable_joke: bool
    kwargs: dict[str, Any]

    @classmethod
    def assign(cls, key: str, disable_joke: bool = False, **kwargs: Any):
        """
        创建多语言消息元素的工厂方法。

        :param key: 多语言的键名（如 "message.list" -> "消息列表"）
        :param disable_joke: 是否禁用玩笑功能（默认为 False）
        :param kwargs: 多语言字符串中的变量（如 name="Alice", count=5）
        :return: I18NContextElement 实例
        """
        return deepcopy(cls(key=key, disable_joke=disable_joke, kwargs=kwargs))

    def kecode(self):
        """
        转换为 KE 码格式。

        多语言消息在 KE 码中表示为 `[KE:i18n,i18nkey=...,param1=val1,...]`

        :return: KE 码格式的字符串
        """
        if self.kwargs:
            # 有参数，将其拼接到 KE 码中
            params = ",".join(f"{k}={v}" for k, v in self.kwargs.items())
            return f"[KE:i18n,i18nkey={self.key},{params}]"
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
    """
    图片消息元素。

    该类用于处理和管理消息中的图片。支持多种输入格式：
    1. 本地文件路径（绝对路径或相对路径）
    2. URL 链接（HTTP/HTTPS）
    3. Base64 编码的图片数据
    4. PIL Image 对象

    属性：
        path: 图片路径或 URL
        need_get: 是否需要从网络获取图片（URL 时为 True）
        headers: 获取网络图片时的请求头字典
        cached_b64: 缓存的 Base64 编码图片数据

    示例：
        > img = ImageElement.assign("/path/to/image.png")
        > img_url = ImageElement.assign("https://example.com/image.png")
    """

    path: str
    need_get: bool = False
    headers: dict[str, Any] | None = None
    cached_b64: str | None = None

    @classmethod
    def assign(cls, path: str | Path | PILImage.Image, headers: dict[str, Any] | None = None):
        """
        创建图片元素的工厂方法。

        支持多种输入类型，会自动进行处理和转换。

        :param path: 图片来源，可以是：
                    - 本地文件路径（str 或 Path）
                    - URL 地址（以 `http://` 或 `https://` 开头）
                    - Base64 编码数据（以 base64 开头）
                    - PIL Image 对象
        :param headers: 获取网络图片时的请求头（如用户代理、认证信息等）
        :return: ImageElement 实例
        """
        need_get = False
        if isinstance(path, PILImage.Image):
            # ========== 处理 PIL Image 对象 ==========
            # 将 PIL Image 保存为本地文件
            save = random_cache_path("png")
            path.convert("RGBA").save(save)
            path = str(save)
        elif isinstance(path, Path):
            # ========== 处理 Path 对象 ==========
            # 转换为字符串路径
            path = str(path)

        # ========== 检查是否是 URL ==========
        if re.match("^https?://.*", path):
            need_get = True
        # ========== 处理 Base64 编码数据 ==========
        elif "base64" in path:
            # 提取 Base64 编码的图片数据
            _, encoded_img = path.split(",", 1)
            img_data = base64.b64decode(encoded_img)

            # 将解码后的数据保存为本地文件
            save = random_cache_path("png")
            with open(save, "wb") as img_file:
                img_file.write(img_data)
            path = save

        return deepcopy(cls(str(path), need_get, headers))

    async def get(self) -> str:
        """
        获取图片的实际路径。

        如果是网络 URL，会自动下载到本地缓存。

        :return: 本地文件路径字符串
        """
        if self.need_get:
            # 从网络下载图片
            return str(await self.get_image())
        # 返回本地路径
        return self.path

    @retry(stop=stop_after_attempt(3))
    async def get_image(self) -> Path:
        """
        从网络下载图片。

        使用 3 次重试机制，每次获取失败后会自动重试。

        :return: 本地缓存文件的 Path 对象
        """
        url = self.path
        async with httpx.AsyncClient() as client:
            # 发送 HTTP GET 请求获取图片
            resp = await client.get(url, timeout=20.0, headers=self.headers)
            raw = resp.content
            # 自动识别图片格式
            ft = filetype.match(raw).extension
            # 保存到缓存目录
            img_path = random_cache_path(ft)
            with open(img_path, "wb+") as image_cache:
                image_cache.write(raw)
            return img_path

    async def get_base64(self, mime: bool = False) -> str:
        """
        获取图片的 Base64 编码字符串。

        可用于嵌入到 HTML 或数据 URI 中。

        :param mime: 是否包含 MIME 类型前缀（如 data:image/png;base64,...）
        :return: Base64 编码的字符串
        """
        # 获取图片文件路径
        file = await self.get()

        # 读取文件并进行 Base64 编码
        with open(file, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("UTF-8")
        self.cached_b64 = img_b64
        # Logger.debug(f"ImageElement: Cached base64 for {file}")

        if mime:
            # 添加 MIME 类型前缀
            mime_type, _ = mimetypes.guess_type(file)
            if not mime_type:
                mime_type = "application/octet-stream"
            self.cached_b64 = f"data:{mime_type};base64,{img_b64}"
            return self.cached_b64
        return img_b64

    async def add_random_noise(self) -> "ImageElement":
        """
        为图片添加随机噪点。

        用于 QQ 侧防止同一图片发送过多触发风控。

        :return: 新的 ImageElement 实例
        """
        # 打开图片
        image = PILImage.open(await self.get())
        image = image.convert("RGBA")

        # 创建噪点图层
        noise_image = PILImage.new("RGBA", (50, 50))
        for i in range(50):
            for j in range(50):
                noise_image.putpixel((i, j), (i, j, i, random.randint(0, 1)))

        # 将噪点合成到原图
        image.alpha_composite(noise_image)

        # 保存处理后的图片
        save = f"{random_cache_path()}.png"
        image.save(save)
        return ImageElement.assign(save)

    def kecode(self):
        """
        转换为 KE 码格式。

        :return: KE 码格式的字符串
        """
        if self.headers:
            # 有请求头，进行 Base64 编码后传递
            headers_b64 = base64.b64encode(orjson.dumps(self.headers)).decode("utf-8")
            return f"[KE:image,path={self.path},headers={headers_b64}]"
        return f"[KE:image,path={self.path}]"

    async def to_PIL_image(self) -> PILImage.Image:
        """
        将图片元素转换为 PIL Image 对象。

        用于对图片进行进一步的处理和操作。

        :return: PIL Image 对象
        """
        path = self.path
        if self.need_get:
            path = await self.get_image()
        return PILImage.open(path)

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()


@define
class VoiceElement(BaseElement):
    """
    语音消息元素。

    该类用于处理消息中的音频/语音文件。支持本地文件路径。

    属性：
        path: 语音文件的本地路径

    示例：
    ```
        > voice = VoiceElement.assign("/path/to/audio.mp3")
        > str(voice)
        '[KE:voice,path=/path/to/audio.mp3]'
    ```
    """

    path: str

    @classmethod
    def assign(cls, path: str | Path):
        """
        创建语音元素的工厂方法。

        :param path: 语音文件的本地路径（str 或 Path 对象）
        :return: VoiceElement 实例
        """
        return deepcopy(cls(str(path)))

    def kecode(self):
        """转换为 KE 码格式"""
        return f"[KE:voice,path={self.path}]"

    def __str__(self):
        """返回 KE 码格式"""
        return self.kecode()


@define
class MentionElement(BaseElement):
    """
    提及元素 - 用于在消息中提及（@）其他用户。

    该类用于创建对消息中用户的引用，会在消息中显示为 @用户名 的形式。

    属性：
        client: 平台/客户端标识（如 "QQ"、"Discord"）
        id: 用户在该平台的唯一标识

    示例：
    ```
        > mention = MentionElement.assign("QQ|123456789")
        > str(mention)
        '<AT:QQ|123456789>'
    ```
    """

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
        # 分割平台标识和用户 ID
        return deepcopy(cls(client=user_id.split("|")[0], id=user_id.split("|")[-1]))

    def kecode(self):
        """转换为 KE 码格式"""
        return f"[KE:mention,userid={self.client}|{self.id}]"

    def __str__(self):
        """返回 AT 码格式"""
        return f"<AT:{self.client}|{self.id}>"


@define
class EmbedFieldElement(BaseElement):
    """
    Embed 字段元素 - 用于构建嵌入式消息的字段。

    该类表示嵌入式消息（Embed）中的一个字段，可以包含标题和值，
    并支持内联显示选项。

    属性：
        name: 字段名称/标题
        value: 字段值/内容
        inline: 是否内联显示（True 表示在同一行显示多个字段）

    示例：
    ```
        > field = EmbedFieldElement.assign("作者", "Alice", inline=True)
    ```
    """

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
    """
    Embed 消息元素 - 用于创建富文本嵌入式消息。

    该类用于构建包含标题、描述、图片、字段等的嵌入式消息，
    常用于展示复杂的信息结构（如卡片、摘要等）。

    属性：
        title: 嵌入消息的标题
        description: 嵌入消息的描述文本
        url: 嵌入消息的跳转链接
        timestamp: 时间戳（用于显示发布时间）
        color: 嵌入消息的颜色（十六进制，如 0x0091FF）
        image: 嵌入消息的主图片
        thumbnail: 嵌入消息的缩略图
        author: 作者信息
        footer: 页脚文本
        fields: 字段列表（EmbedFieldElement 对象列表）

    示例：
    ```
        > embed = EmbedElement.assign(
        ...     title="标题",
        ...     description="描述文本",
        ...     color=0xFF0000
        ... )
    ```
    """

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
        """
        将 Embed 转换为消息链。

        将嵌入式消息转换为可直接发送的消息链列表，用于兼容不支持 Embed 格式的平台。

        :param session_info: 会话信息，用于多语言翻译和格式化
        :return: 消息元素列表
        """
        text_lst = []

        # ========== 收集文本内容 ==========
        if self.title:
            text_lst.append(self.title)
        if self.description:
            text_lst.append(self.description)
        if self.url:
            text_lst.append(self.url)

        # ========== 添加字段 ==========
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

        # ========== 添加作者信息 ==========
        if self.author:
            if session_info:
                text_lst.append(
                    f"{session_info.locale.t('message.embed.author')}{session_info.locale.t_str(self.author)}"
                )
            else:
                text_lst.append(f"Author: {self.author}")

        # ========== 添加页脚 ==========
        if self.footer:
            if session_info:
                text_lst.append(session_info.locale.t_str(self.footer))
            else:
                text_lst.append(self.footer)

        # ========== 构建消息链 ==========
        message_chain = []
        if text_lst:
            # 添加文本元素
            message_chain.append(PlainElement.assign("\n".join(text_lst)))
        if self.image:
            # 添加主图片
            message_chain.append(self.image)

        return message_chain

    def kecode(self):
        """... KE 码格式未实现 ..."""

    def __str__(self):
        """返回消息链的字符串表示"""
        return str(self.to_message_chain())


@define
class RawElement(BaseElement):
    """
    原始元素 - 用于包含未处理的原始数据。

    该类用于传递不需要特殊处理的原始数据，可以是任何字符串内容，原则上不应该被主动使用。

    通常用于包含预格式化的文本或特殊的元数据。

    属性：
        value: 原始值/数据

    示例：
    ```
        > raw = RawElement.assign("<custom>data</custom>")
        > str(raw)
        '<custom>data</custom>'
    ```
    """

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
    "URLElement",
    "FormattedTimeElement",
    "I18NContextElement",
    "ImageElement",
    "VoiceElement",
    "EmbedFieldElement",
    "EmbedElement",
    "MentionElement",
    "RawElement",
]
