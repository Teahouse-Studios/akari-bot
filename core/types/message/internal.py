from typing import Union, List

from PIL import Image as PImage


class Plain:
    """
    文本消息。
    """

    def __init__(self, text, *texts):
        """
        :param text: 文本内容
        """
        self.text = str(text)
        for t in texts:
            self.text += str(t)


class Url:
    """
    URL消息。
    """

    mm = False
    disable_mm = False

    def __init__(self, url: str, use_mm: bool = False, disable_mm: bool = False):
        """
        :param url: URL
        :param use_mm: 是否使用跳转链接，覆盖全局设置
        :param disable_mm: 是否禁用跳转链接，覆盖全局设置
        """
        self.url = url
        self.mm = use_mm
        self.disable_mm = disable_mm


class ErrorMessage:
    """
    错误消息。
    """

    def __init__(self, error_message):
        """
        :param error_message: 错误信息文本
        """
        self.error_message = error_message


class Image:
    """
    图片消息。
    """

    def __init__(self,
                 path: Union[str, PImage.Image], headers=None):
        """
        :param path: 图片路径或PIL.Image对象
        :param headers: 获取图片时的请求头
        """
        self.need_get = False
        self.path = path
        self.headers = headers

    async def get(self):
        """
        获取图片。
        """

    async def get_image(self):
        """
        从网络下载图片。
        """


class Voice:
    """
    语音消息。
    """

    def __init__(self,
                 path=None):
        """
        :param path: 语音文件路径。
        """
        self.path = path


class EmbedField:
    """
    Embed消息的字段。
    """

    def __init__(self,
                 name: str = None,
                 value: str = None,
                 inline: bool = False):
        """
        :param name: 字段名
        :param value: 字段值
        :param inline: 是否为行内字段
        """
        self.name = name
        self.value = value
        self.inline = inline


class Embed:
    """
    Embed消息。
    """

    def __init__(self,
                 title: str = None,
                 description: str = None,
                 url: str = None,
                 timestamp: float = None,
                 color: int = None,
                 image: Image = None,
                 thumbnail: Image = None,
                 author: str = None,
                 footer: str = None,
                 fields: List[EmbedField] = None):
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
        self.fields = fields

    def to_msgchain(self):
        """
        将Embed转换为消息链。
        """


__all__ = ["Plain", "Image", "Voice", "Embed", "EmbedField", "Url", "ErrorMessage"]
