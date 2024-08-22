from typing import Union, List, Tuple

from .internal import Plain, Image, Voice, Embed, Url


class MessageChain:
    """
    消息链。
    """

    def __init__(self, elements: Union[str, List[Union[Plain, Image, Voice, Embed, Url]],
                                       Tuple[Union[Plain, Image, Voice, Embed, Url]],
                                       Plain, Image, Voice, Embed, Url] = None):
        """
        :param elements: 消息链元素
        """
        self.value = elements

    @property
    def is_safe(self) -> bool:
        """
        检查消息链是否安全。
        """
        raise NotImplementedError

    def as_sendable(self, msg, embed=True) -> list:
        """
        将消息链转换为可发送的格式。
        """
        raise NotImplementedError

    def to_list(self) -> list:
        """
        将消息链转换为列表。
        """
        raise NotImplementedError

    def from_list(self, lst: list):
        """
        从列表构造消息链。
        """
        raise NotImplementedError

    def append(self, element):
        """
        添加一个消息链元素到末尾。
        """
        raise NotImplementedError

    def remove(self, element):
        """
        删除一个消息链元素。
        """
        raise NotImplementedError


__all__ = ["MessageChain"]
