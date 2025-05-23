from __future__ import annotations

import base64
import html
import re
from copy import deepcopy
from typing import List, Optional, Tuple, Union, Any
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import orjson as json

from core.builtins.message.elements import (
    BaseElement,
    PlainElement,
    EmbedElement,
    FormattedTimeElement,
    I18NContextElement,
    URLElement,
    ImageElement,
    VoiceElement,
    MentionElement,
)
from core.exports import add_export

if TYPE_CHECKING:
    from core.builtins.session import SessionInfo

from core.builtins.utils import Secret
from core.builtins.types import MessageElement
from core.builtins.converter import converter
from core.joke import shuffle_joke as joke
from core.logger import Logger
from core.utils.http import url_pattern

from attrs import define


@define
class MessageChain:
    """
    消息链。
    """

    values: List[MessageElement]

    @classmethod
    def assign(
        cls,
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
        values = []
        if isinstance(elements, MessageChain):
            return elements
        if isinstance(elements, str):
            elements = match_kecode(elements)
        if isinstance(elements, BaseElement):
            if isinstance(elements, PlainElement):
                if elements.text != "":
                    elements = match_kecode(elements.text, elements.disable_joke)
            else:
                elements = [elements]
        if isinstance(elements, dict):
            for key in elements:
                elements = converter.structure(elements[key], MessageElement)
        if isinstance(elements, (list, tuple)):
            for e in elements:
                if isinstance(e, str):
                    if e != "":
                        values += match_kecode(e)
                elif isinstance(e, dict):
                    for key in e:
                        tmp_e = converter.structure(e[key], MessageElement)
                        if isinstance(tmp_e, PlainElement):
                            if tmp_e.text != "":
                                values += match_kecode(tmp_e.text, tmp_e.disable_joke)
                        else:
                            values.append(tmp_e)

                elif isinstance(e, PlainElement):
                    if isinstance(e, PlainElement):
                        if e.text != "":
                            values += match_kecode(e.text, e.disable_joke)

                elif isinstance(e, BaseElement):
                    values.append(e)
                else:
                    Logger.error(f"Unexpected message type: {e}")
        elif not elements:
            pass
        else:
            Logger.error(f"Unexpected message type: {elements}")
        # Logger.debug(f"MessageChain: {self.value}")
        # Logger.debug("Elements: " + str(elements))
        return deepcopy(cls(values))

    @property
    def is_safe(self) -> bool:
        """
        检查消息链是否安全。
        """

        def unsafeprompt(name, secret, text):
            return f"{name} contains unsafe text \"{secret}\": {text}"

        for v in self.values:
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

    def as_sendable(self, session_info: SessionInfo = None, embed: bool = True) -> list:
        """
        将消息链转换为可发送的格式。
        """
        value = []
        for x in self.values:
            if isinstance(x, EmbedElement) and not embed:
                value += x.to_message_chain()
            elif isinstance(x, PlainElement):
                if session_info:
                    if x.text != "":
                        x.text = session_info.locale.t_str(x.text)
                    else:
                        x = PlainElement.assign(session_info.locale.t("error.message.chain.plain.empty"))
                value.append(x)
            elif isinstance(x, FormattedTimeElement):
                x = x.to_str(session_info)
                if value and isinstance(value[-1], PlainElement):
                    if not value[-1].text.endswith("\n"):
                        value[-1].text += "\n"
                    value[-1].text += x
                else:
                    value.append(PlainElement.assign(x))
            elif isinstance(x, I18NContextElement):
                for k, v in x.kwargs.items():
                    if isinstance(v, str):
                        x.kwargs[k] = session_info.locale.t_str(v)
                t_value = session_info.locale.t(x.key, **x.kwargs)
                if isinstance(t_value, str):
                    value.append(PlainElement.assign(t_value, disable_joke=x.disable_joke))
                else:
                    value += MessageChain.assign(t_value).as_sendable(session_info)
            elif isinstance(x, URLElement):
                value.append(PlainElement.assign(x.url, disable_joke=True))
            else:
                value.append(x)
        if not value:
            if session_info:
                value.append(PlainElement.assign(session_info.locale.t("error.message.chain.plain.empty")))
        for x in value:
            if isinstance(x, PlainElement) and not x.disable_joke:
                x.text = joke(x.text)

        return value

    def to_str(self, safe=True) -> str:
        """
        将消息链转换为字符串。

        :param safe: 是否安全模式，默认开启，开启后图片等路径将不会转换。
        """
        result = ""
        for x in self.values:
            if isinstance(x, PlainElement):
                result += x.text
            else:
                if safe:
                    result += str(x)

        return result

    def to_list(self) -> list[dict[str, Any]]:
        """
        将消息链序列化为列表。
        """
        return [converter.unstructure(x, MessageElement) for x in self.values]

    @classmethod
    def from_list(cls, lst: list) -> MessageChain:
        """
        从列表构造消息链，返回新的消息链。
        """
        converted = []
        for x in lst:
            for elem in x:
                converted.append(converter.structure(elem, MessageElement))
        return deepcopy(cls(converted))

    def append(self, element):
        """
        添加一个消息链元素到末尾。
        """
        self.values.append(element)

    def remove(self, element):
        """
        删除一个消息链元素。
        """
        self.values.remove(element)

    def insert(self, index, element):
        """
        在指定位置插入一个消息链元素。
        """
        self.values.insert(index, element)

    def copy(self):
        """
        复制一个消息链。
        """
        return MessageChain.assign(self.values.copy())

    def __str__(self):
        return f"[{", ".join([x.__repr__() for x in self.values])}]"

    def __iter__(self):
        return iter(self.values)

    def __add__(self, other):
        if isinstance(other, MessageChain):
            return MessageChain.assign(self.values + other.values)
        if isinstance(other, list):
            return MessageChain.assign(self.values + other)
        raise TypeError(
            f"Unsupported operand type(s) for +: \"MessageChain\" and \"{type(other).__name__}\""
        )

    def __radd__(self, other):
        if isinstance(other, MessageChain):
            return MessageChain.assign(other.values + self.values)
        if isinstance(other, list):
            return MessageChain.assign(other + self.values)
        raise TypeError(
            f"Unsupported operand type(s) for +: \"{type(other).__name__}\" and \"MessageChain\""
        )

    def __iadd__(self, other):
        if isinstance(other, MessageChain):
            self.values += other.values
        elif isinstance(other, list):
            self.values += other
        else:
            raise TypeError(
                f"Unsupported operand type(s) for +=: \"MessageChain\" and \"{type(other).__name__}\""
            )
        return self


def match_kecode(text: str,
                 disable_joke: bool = False) -> List[Union[PlainElement,
                                                           ImageElement,
                                                           VoiceElement,
                                                           I18NContextElement]]:
    split_all = re.split(r"(\[Ke:.*?])", text)
    split_all = [x for x in split_all if x]
    elements = []
    params = []

    for e in split_all:
        match = re.match(r"\[Ke:([^\s,\]]+)(?:,([^\]]+))?\]", e)
        if not match:
            if e != "":
                elements.append(PlainElement.assign(e, disable_joke=disable_joke))
        else:
            element_type = match.group(1).lower()

            if match.group(2):
                params = match.group(2).split(",")
                params = [x for x in params if x]

            if element_type == "plain":
                for a in params:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "text":
                            ua = html.unescape(ma.group(2))
                            elements.append(PlainElement.assign(ua, disable_joke=disable_joke))
                        else:
                            a = html.unescape(a)
                            elements.append(PlainElement.assign(a, disable_joke=disable_joke))
                    else:
                        a = html.unescape(a)
                        elements.append(PlainElement.assign(a, disable_joke=disable_joke))
            elif element_type == "image":
                for a in params:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        img = None
                        if ma.group(1) == "path":
                            parse_url = urlparse(ma.group(2))
                            if parse_url[0] == "file" or url_pattern.match(parse_url[1]):
                                img = ImageElement.assign(path=ma.group(2))
                        if ma.group(1) == "headers" and img:
                            img.headers = json.loads(str(base64.b64decode(ma.group(2)), "UTF-8"))
                        if img:
                            elements.append(img)
                        else:
                            a = html.unescape(a)
                            elements.append(ImageElement.assign(a))
                    else:
                        a = html.unescape(a)
                        elements.append(ImageElement.assign(a))
            elif element_type == "voice":
                for a in params:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "path":
                            parse_url = urlparse(ma.group(2))
                            if parse_url[0] == "file" or url_pattern.match(parse_url[1]):
                                elements.append(VoiceElement.assign(ma.group(2)))
                        else:
                            a = html.unescape(a)
                            elements.append(VoiceElement.assign(a))
                    else:
                        a = html.unescape(a)
                        elements.append(VoiceElement.assign(a))
            elif element_type == "i18n":
                i18nkey = None
                kwargs = {}
                for a in params:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "i18nkey":
                            i18nkey = html.unescape(ma.group(2))
                        else:
                            kwargs[ma.group(1)] = html.unescape(ma.group(2))
                if i18nkey:
                    elements.append(I18NContextElement.assign(i18nkey, disable_joke, **kwargs))
            elif element_type == "mention":
                for a in params:
                    ma = re.match(r"(.*?)=(.*)", a)
                    if ma:
                        if ma.group(1) == "userid":
                            ua = html.unescape(ma.group(2))
                            elements.append(MentionElement.assign(ua))
                        else:
                            a = html.unescape(a)
                            elements.append(MentionElement.assign(a))
                    else:
                        a = html.unescape(a)
                        elements.append(MentionElement.assign(a))

    return elements


add_export(MessageChain)


__all__ = ["MessageChain"]
