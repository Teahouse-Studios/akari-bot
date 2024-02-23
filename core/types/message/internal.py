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
        raise NotImplementedError


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
        raise NotImplementedError


class ErrorMessage:
    """
    错误消息。
    """

    def __init__(self, error_message):
        """
        :param error_message: 错误信息文本
        """
        raise NotImplementedError


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
        raise NotImplementedError

    async def get(self):
        """
        获取图片。
        """
        raise NotImplementedError

    async def get_image(self):
        """
        从网络下载图片。
        """
        raise NotImplementedError


class Voice:
    """
    语音消息。
    """

    def __init__(self,
                 path=None):
        """
        :param path: 语音文件路径。
        """
        raise NotImplementedError


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
        raise NotImplementedError


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
        raise NotImplementedError

    def to_message_chain(self, msg):
        """
        将Embed转换为消息链。
        """
        raise NotImplementedError


__all__ = ["Plain", "Image", "Voice", "Embed", "EmbedField", "Url", "ErrorMessage"]
