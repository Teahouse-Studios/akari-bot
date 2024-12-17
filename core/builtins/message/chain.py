from __future__ import annotations

import base64
import re
from typing import List, Optional, Tuple, Union, Any
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import orjson as json

from core.builtins.message.elements import (
    elements_map,
    MessageElement,
    PlainElement,
    EmbedElement,
    ErrorMessageElement,
    FormattedTimeElement,
    I18NContextElement,
    URLElement,
    ImageElement,
    VoiceElement,
)

if TYPE_CHECKING:
    from core.builtins.message import MessageSession

from core.builtins.utils import Secret
from core.logger import Logger

from core.utils.http import url_pattern

from cattrs import structure, unstructure


class MessageChain:
    """
    消息链。
    """

    def __init__(
        self,
        elements: Optional[
            Union[
                str,
                List[MessageElement],
                Tuple[MessageElement],
                MessageElement,
                MessageChain,
            ]
        ] = None,
    ):
        """
        :param elements: 消息链元素。
        """
        self.value = []
        if isinstance(elements, MessageChain):
            self.value = elements.value
            return
        if isinstance(elements, str):
            elements = match_kecode(elements)
        if isinstance(elements, MessageElement):
            if isinstance(elements, PlainElement):
                if elements.text != "":
                    elements = match_kecode(elements.text)
            else:
                elements = [elements]
        if isinstance(elements, dict):
            for key in elements:
                if key in elements_map:
                    elements = [structure(elements[key], elements_map[key])]
                else:
                    Logger.error(f"Unexpected message type {key}: {elements}")
        if isinstance(elements, (list, tuple)):
            for e in elements:
                if isinstance(e, str):
                    if e != "":
                        self.value += match_kecode(e)
                elif isinstance(e, dict):
                    for key in e:
                        if key in elements_map:
                            tmp_e = structure(e[key], elements_map[key])
                            if isinstance(tmp_e, PlainElement):
                                if tmp_e.text != "":
                                    self.value += match_kecode(tmp_e.text)
                            else:
                                self.value.append(tmp_e)
                        else:
                            Logger.error(f"Unexpected message type {key}: {e}")

                elif isinstance(e, PlainElement):
                    if isinstance(e, PlainElement):
                        if e.text != "":
                            self.value += match_kecode(e.text)

                elif isinstance(e, MessageElement):
                    self.value.append(e)
                else:
                    Logger.error(f"Unexpected message type: {e}")
        elif not elements:
            pass
        else:
            Logger.error(f"Unexpected message type: {elements}")
        # Logger.debug(f"MessageChain: {self.value}")
        # Logger.debug("Elements: " + str(elements))

    @property
    def is_safe(self) -> bool:
        """
        检查消息链是否安全。
        """

        def unsafeprompt(name, secret, text):
            return f'{name} contains unsafe text "{secret}": {text}'

        for v in self.value:
            if isinstance(v, PlainElement):
                for secret in Secret.list:
                    if secret in ["", None, True, False]:
                        continue
                    if v.text.upper().find(secret.upper()) != -1:
                        Logger.warning(unsafeprompt("Plain", secret, v.text))
                        return False
            elif isinstance(v, EmbedElement):
                for secret in Secret.list:
                    if secret in ["", None, True, False]:
                        continue
                    if v.title:
                        if v.title.upper().find(secret.upper()) != -1:
                            Logger.warning(unsafeprompt("Embed.title", secret, v.title))
                            return False
                    if v.description:
                        if v.description.upper().find(secret.upper()) != -1:
                            Logger.warning(
                                unsafeprompt("Embed.description", secret, v.description)
                            )
                            return False
                    if v.footer:
                        if v.footer.upper().find(secret.upper()) != -1:
                            Logger.warning(
                                unsafeprompt("Embed.footer", secret, v.footer)
                            )
                            return False
                    if v.author:
                        if v.author.upper().find(secret.upper()) != -1:
                            Logger.warning(
                                unsafeprompt("Embed.author", secret, v.author)
                            )
                            return False
                    if v.url:
                        if v.url.upper().find(secret.upper()) != -1:
                            Logger.warning(unsafeprompt("Embed.url", secret, v.url))
                            return False
                    for f in v.fields:
                        if f.name.upper().find(secret.upper()) != -1:
                            Logger.warning(
                                unsafeprompt("Embed.field.name", secret, f.name)
                            )
                            return False
                        if f.value.upper().find(secret.upper()) != -1:
                            Logger.warning(
                                unsafeprompt("Embed.field.value", secret, f.value)
                            )
                            return False
        return True

    def as_sendable(self, msg: MessageSession = None, embed: bool = True) -> list:
        """
        将消息链转换为可发送的格式。
        """
        locale = None
        if msg:
            locale = msg.locale.locale
        value = []
        for x in self.value:
            if isinstance(x, EmbedElement) and not embed:
                value += x.to_message_chain(msg)
            elif isinstance(x, PlainElement):
                if x.text != "":
                    value.append(x)
                else:
                    value.append(
                        PlainElement.assign(
                            str(
                                ErrorMessageElement.assign(
                                    "{error.message.chain.plain.empty}", locale=locale
                                )
                            )
                        )
                    )
            elif isinstance(x, FormattedTimeElement):
                x = x.to_str(msg=msg)
                if value and isinstance(value[-1], PlainElement):
                    if not value[-1].text.endswith("\n"):
                        value[-1].text += "\n"
                    value[-1].text += x
                else:
                    value.append(PlainElement.assign(x))
            elif isinstance(x, I18NContextElement):
                t_value = msg.locale.t(x.key, **x.kwargs)
                if isinstance(t_value, str):
                    value.append(PlainElement.assign(t_value))
                else:
                    value += MessageChain(t_value).as_sendable(msg)
            elif isinstance(x, URLElement):
                value.append(PlainElement.assign(x.url, disable_joke=True))
            elif isinstance(x, ErrorMessageElement):
                value.append(PlainElement.assign(str(x)))
            else:
                value.append(x)
        if not value:
            value.append(
                PlainElement.assign(
                    str(
                        ErrorMessageElement.assign(
                            "{error.message.chain.plain.empty}", locale=locale
                        )
                    )
                )
            )
        return value

    def to_list(self) -> list[dict[str, Any]]:
        """
        将消息链序列化为列表。
        """
        return [{x.__name__(): unstructure(x)} for x in self.value]

    def from_list(self, lst: list) -> None:
        """
        从列表构造消息链，替换原有的消息链。
        """
        converted = []
        for x in lst:
            for elem in x:
                if elem in elements_map:
                    converted.append(structure(x[elem], elements_map[elem]))
                else:
                    Logger.error(f"Unexpected message type: {elem}")
        self.value = converted

    def append(self, element):
        """
        添加一个消息链元素到末尾。
        """
        self.value.append(element)

    def remove(self, element):
        """
        删除一个消息链元素。
        """
        self.value.remove(element)

    def insert(self, index, element):
        """
        在指定位置插入一个消息链元素。
        """
        self.value.insert(index, element)

    def copy(self):
        """
        复制一个消息链。
        """
        return MessageChain(self.value.copy())

    def __str__(self):
        return f'[{", ".join([x.__repr__() for x in self.value])}]'

    def __repr__(self):
        return self.__str__()

    def __iter__(self):
        return iter(self.value)

    def __add__(self, other):
        if isinstance(other, MessageChain):
            return MessageChain(self.value + other.value)
        if isinstance(other, list):
            return MessageChain(self.value + other)
        raise TypeError(
            f"Unsupported operand type(s) for +: 'MessageChain' and '{type(other).__name__}'"
        )

    def __radd__(self, other):
        if isinstance(other, MessageChain):
            return MessageChain(other.value + self.value)
        if isinstance(other, list):
            return MessageChain(other + self.value)
        raise TypeError(
            f"Unsupported operand type(s) for +: '{type(other).__name__}' and 'MessageChain'"
        )

    def __iadd__(self, other):
        if isinstance(other, MessageChain):
            self.value += other.value
        elif isinstance(other, list):
            self.value += other
        else:
            raise TypeError(
                f"Unsupported operand type(s) for +=: 'MessageChain' and '{type(other).__name__}'"
            )
        return self


def match_kecode(text: str) -> List[Union[PlainElement, ImageElement, VoiceElement]]:
    split_all = re.split(r"(\[Ke:.*?])", text)
    split_all = [x for x in split_all if x]
    elements = []
    for e in split_all:
        match = re.match(r"\[Ke:(.*?),(.*)]", e)
        if not match:
            if e != "":
                elements.append(PlainElement.assign(e))
        else:
            element_type = match.group(1).lower()
            args = re.split(r",|,.\s", match.group(2))
            for x in args:
                if not x:
                    args.remove("")
            if element_type == "plain":
                for a in args:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "text":
                            elements.append(PlainElement.assign(ma.group(2)))
                        else:
                            elements.append(PlainElement.assign(a))
                    else:
                        elements.append(PlainElement.assign(a))
            elif element_type == "image":
                for a in args:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        img = None
                        if ma.group(1) == "path":
                            parse_url = urlparse(ma.group(2))
                            if parse_url[0] == "file" or url_pattern.match(
                                parse_url[1]
                            ):
                                img = ImageElement.assign(path=ma.group(2))
                        if ma.group(1) == "headers":
                            img.headers = json.loads(
                                str(base64.b64decode(ma.group(2)), "UTF-8")
                            )
                        if img:
                            elements.append(img)
                    else:
                        elements.append(ImageElement.assign(a))
            elif element_type == "voice":
                for a in args:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "path":
                            parse_url = urlparse(ma.group(2))
                            if parse_url[0] == "file" or url_pattern.match(
                                parse_url[1]
                            ):
                                elements.append(VoiceElement.assign(ma.group(2)))
                        else:
                            elements.append(VoiceElement.assign(a))
                    else:
                        elements.append(VoiceElement.assign(a))
    return elements


__all__ = ["MessageChain"]
