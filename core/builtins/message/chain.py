from __future__ import annotations

import base64
import html
import re
from cattrs import structure, unstructure
from typing import List, Optional, Tuple, Union, Any
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import orjson as json

from core.constants import Secret
from core.joke import shuffle_joke as joke
from core.logger import Logger
from core.utils.http import url_pattern
from .elements import (
    elements_map,
    MessageElement,
    PlainElement,
    EmbedElement,
    FormattedTimeElement,
    I18NContextElement,
    URLElement,
    ImageElement,
    VoiceElement,
    MentionElement,
)

if TYPE_CHECKING:
    from core.builtins.message import MessageSession


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
                    elements = match_kecode(elements.text, elements.disable_joke)
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
                                    self.value += match_kecode(tmp_e.text, tmp_e.disable_joke)
                            else:
                                self.value.append(tmp_e)
                        else:
                            Logger.error(f"Unexpected message type {key}: {e}")

                elif isinstance(e, PlainElement):
                    if isinstance(e, PlainElement):
                        if e.text != "":
                            self.value += match_kecode(e.text, e.disable_joke)

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
            return f"{name} contains unsafe text \"{secret}\": {text}"

        for v in self.value:
            if isinstance(v, PlainElement):
                if secret := Secret.check(v.text):
                    Logger.warning(unsafeprompt("Plain", secret, v.text))
                    return False
            elif isinstance(v, EmbedElement):
                if v.title:
                    if secret := Secret.check(v.title):
                        Logger.warning(unsafeprompt("Embed.title", secret, v.title))
                        return False
                if v.description:
                    if secret := Secret.check(v.description):
                        Logger.warning(
                            unsafeprompt("Embed.description", secret, v.description)
                        )
                        return False
                if v.footer:
                    if secret := Secret.check(v.footer):
                        Logger.warning(
                            unsafeprompt("Embed.footer", secret, v.footer)
                        )
                        return False
                if v.author:
                    if secret := Secret.check(v.author):
                        Logger.warning(
                            unsafeprompt("Embed.author", secret, v.author)
                        )
                        return False
                if v.url:
                    if secret := Secret.check(v.url):
                        Logger.warning(unsafeprompt("Embed.url", secret, v.url))
                        return False
                if v.fields:
                    for f in v.fields:
                        if secret := Secret.check(f.name):
                            Logger.warning(
                                unsafeprompt("Embed.field.name", secret, f.name)
                            )
                            return False
                        if secret := Secret.check(f.value):
                            Logger.warning(
                                unsafeprompt("Embed.field.value", secret, f.value)
                            )
                            return False
        return True

    def as_sendable(self, msg: Optional[MessageSession] = None, embed: bool = True) -> list:
        """
        将消息链转换为可发送的格式。
        """
        value = []
        for x in self.value:
            if isinstance(x, EmbedElement) and not embed:
                value += x.to_message_chain(msg)
            elif isinstance(x, PlainElement):
                if msg:
                    if x.text != "":
                        x.text = msg.locale.t_str(x.text)
                    else:
                        x = PlainElement.assign(msg.locale.t("error.message.chain.plain.empty"))
                value.append(x)
            elif isinstance(x, FormattedTimeElement):
                x = x.to_str(msg=msg)
                if value and isinstance(value[-1], PlainElement):
                    if not value[-1].text.endswith("\n"):
                        value[-1].text += "\n"
                    value[-1].text += x
                else:
                    value.append(PlainElement.assign(x))
            elif isinstance(x, I18NContextElement):
                if msg:
                    for k, v in x.kwargs.items():
                        if isinstance(v, str):
                            x.kwargs[k] = msg.locale.t_str(v)
                    t_value = msg.locale.t(x.key, **x.kwargs)
                    value.append(PlainElement.assign(t_value, disable_joke=x.disable_joke))
                else:
                    value.append(PlainElement.assign(f"{{I18N:{x.key}}}", disable_joke=x.disable_joke))
            elif isinstance(x, URLElement):
                value.append(PlainElement.assign(x.url, disable_joke=True))
            else:
                value.append(x)
        if not value:
            if msg:
                value.append(PlainElement.assign(msg.locale.t("error.message.chain.plain.empty")))
        for x in value:
            if isinstance(x, PlainElement) and not x.disable_joke:
                x.text = joke(x.text)

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
        return f"[{", ".join([x.__repr__() for x in self.value])}]"

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
            f"Unsupported operand type(s) for +: \"MessageChain\" and \"{type(other).__name__}\""
        )

    def __radd__(self, other):
        if isinstance(other, MessageChain):
            return MessageChain(other.value + self.value)
        if isinstance(other, list):
            return MessageChain(other + self.value)
        raise TypeError(
            f"Unsupported operand type(s) for +: \"{type(other).__name__}\" and \"MessageChain\""
        )

    def __iadd__(self, other):
        if isinstance(other, MessageChain):
            self.value += other.value
        elif isinstance(other, list):
            self.value += other
        else:
            raise TypeError(
                f"Unsupported operand type(s) for +=: \"MessageChain\" and \"{type(other).__name__}\""
            )
        return self


def _extract_kecode_blocks(text):
    result = []
    i = 0
    while i < len(text):
        if text.startswith("[KE:", i):
            start = i
            i += 4  # Skip "[KE:"
            depth = 1
            while i < len(text):
                if text.startswith("[KE:", i):
                    break
                if text[i] == "]" and depth == 1:
                    i += 1
                    result.append(text[start:i])
                    break
                if text[i] == "]":
                    depth -= 1
                    i += 1
                else:
                    i += 1
            else:
                result.append(text[start:])
                break
        else:
            start = i
            while i < len(text) and not text.startswith("[KE:", i):
                i += 1
            result.append(text[start:i])
    return result


def match_kecode(text: str,
                 disable_joke: bool = False) -> List[Union[
                     PlainElement, ImageElement, VoiceElement,
                     I18NContextElement, MentionElement]]:
    split_all = _extract_kecode_blocks(text)
    split_all = [x for x in split_all if x]
    elements = []

    for e in split_all:
        match = re.match(r"\[KE:([^\s,\]]+)(?:,(.*))?\]$", e, re.DOTALL)
        if not match:
            if e != "":
                elements.append(PlainElement.assign(e, disable_joke=disable_joke))
        else:
            element_type = match.group(1).lower()
            param_str = match.group(2) or ""

            params = []
            buf = ""
            stack = []
            for ch in param_str:
                if ch == "," and not stack:
                    params.append(buf)
                    buf = ""
                else:
                    buf += ch
                    if ch in "[{(<":
                        stack.append(ch)
                    elif ch in "]})>":
                        if stack:
                            stack.pop()
            if buf:
                params.append(buf)

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


def match_atcode(text: str, client: str, pattern: str) -> str:
    def _replacer(match):
        match_client = match.group(1)
        user_id = match.group(2)
        if match_client == client:
            return pattern.replace("{uid}", user_id)
        return match.group(0)

    return re.sub(r"<(?:AT|@):([^\|]+)\|(?:.*?\|)?([^\|>]+)>", _replacer, text)


__all__ = ["MessageChain"]
