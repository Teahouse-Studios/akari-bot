from __future__ import annotations

import base64
import html
import random
import re
from copy import deepcopy
from typing import List, Optional, Tuple, Union, Any
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import orjson

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
from core.constants import Secret, default_locale
from core.exports import add_export
from core.i18n import Locale

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo

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
        if isinstance(elements, MessageChain):
            return elements
        values = []
        if isinstance(elements, str):
            elements = PlainElement.assign(elements)
        if isinstance(elements, BaseElement):
            elements = [elements]
        if isinstance(elements, dict):
            for key in elements:
                elements = converter.structure(elements[key], MessageElement)
        if isinstance(elements, (list, tuple)):
            for e in elements:
                if isinstance(e, str) and e:
                    values.append(PlainElement.assign(e))
                elif isinstance(e, dict):
                    for key in e:
                        tmp_e = converter.structure(e[key], MessageElement)
                        values.append(tmp_e)

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

    def as_sendable(self, session_info: SessionInfo = None, parse_message: bool = True) -> list:
        """
        将消息链转换为可发送的格式。
        """
        value = []
        support_embed = True
        if session_info:
            support_embed = session_info.support_embed
        for x in self.values:
            if isinstance(x, EmbedElement) and not support_embed:
                value += x.to_message_chain(session_info)
            elif isinstance(x, PlainElement):
                if session_info:
                    if x.text != "":
                        if parse_message:
                            x.text = session_info.locale.t_str(x.text)
                            element_chain = match_kecode(x.text, x.disable_joke)
                            for elem in element_chain.values:
                                elem = MessageChain.assign(elem).as_sendable(session_info, parse_message=False)
                                if isinstance(elem, PlainElement):
                                    elem.text = session_info.locale.t_str(elem.text)
                                value += elem
                            continue
                    else:
                        x = PlainElement.assign(session_info.locale.t("error.message.chain.empty"))
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
                if not session_info:
                    locale = Locale(default_locale)
                else:
                    locale = session_info.locale
                for k, v in x.kwargs.items():
                    if isinstance(v, str):
                        x.kwargs[k] = locale.t_str(v)
                t_value = locale.t(x.key, **x.kwargs)
                if isinstance(t_value, str):
                    value.append(PlainElement.assign(t_value, disable_joke=x.disable_joke))
                else:
                    value += MessageChain.assign(t_value).as_sendable(session_info)
            elif isinstance(x, URLElement):
                if session_info and (session_info.use_url_manager and x.applied_mm is None):
                    x = URLElement.assign(x.url, use_mm=True, md_format_name=x.md_format_name)
                if session_info and session_info.use_url_md_format and not x.applied_md_format:
                    x = URLElement.assign(x.url, md_format=True, md_format_name=x.md_format_name)

                value.append(PlainElement.assign(x.url, disable_joke=True))
            else:
                value.append(x)
        if not value:
            if session_info:
                value.append(PlainElement.assign(session_info.locale.t("error.message.chain.empty")))
        for x in value:
            if isinstance(x, PlainElement) and not x.disable_joke:
                x.text = joke(x.text)

        return value

    def to_str(self, text_only=True, element_filter: tuple[MessageElement] = None) -> str:
        """
        将消息链转换为字符串。

        :param text_only: 是否仅转换文本元素为字符串，默认为True。
        :param element_filter: 可选的元素过滤器，指定哪些元素类型需要被转换为字符串。
        """
        result = ""
        for x in self.values:
            if element_filter and not isinstance(x, element_filter):
                continue
            if isinstance(x, PlainElement):
                result += x.text
            else:
                if not text_only:
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

    def __len__(self):
        return len(self.values)

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


@define
class I18NMessageChain:
    """
    多语言消息链，适用于不同语言环境下的消息处理。优先级为 PlatformMessageChain > I18NMessageChain > MessageChain，使用时须保证嵌套关系正确。
    """

    values: dict[str, MessageChain]

    @classmethod
    def assign(cls, values: dict[str, MessageChain]) -> I18NMessageChain:
        """
        :param values: 多语言消息链元素，键为语言代码，值为消息链。必须包含 `default` 键用于回滚处理。
        """
        if not isinstance(values, dict):
            raise TypeError("I18NMessageChain values must be a dictionary.")
        if "default" not in values:
            raise ValueError("I18NMessageChain values must have \"default\" key.")
        return cls(values=deepcopy(values))


@define
class PlatformMessageChain:
    """
    平台消息链，适用于不同平台的消息处理。优先级为 PlatformMessageChain > I18NMessageChain > MessageChain，使用时须保证嵌套关系正确。
    """

    values: dict[str, Union[MessageChain, I18NMessageChain]]

    @classmethod
    def assign(cls, values: dict[str, Union[MessageChain, I18NMessageChain]]) -> PlatformMessageChain:
        """
        :param values: 平台消息链元素，键为平台名称，值为消息链。必须包含 `default` 键用于回滚处理。
        """
        if not isinstance(values, dict):
            raise TypeError("PlatformMessageChain values must be a dictionary.")
        return cls(values=deepcopy(values))


@define
class MessageNodes:
    """
    消息节点列表。

    """

    values: List[MessageChain]
    name: str = ""

    @classmethod
    def assign(cls, values: List[MessageChain], name: Optional[str] = None):
        """
        :param values: 节点列表。
        :param name: 节点名称，默认为随机生成的字符串。
        """
        if not name:
            name = "Message " + "".join(random.sample("abcdefghijklmnopqrstuvwxyz", 5))

        return cls(values=values, name=name)

    @property
    def is_safe(self) -> bool:
        """
        检查消息节点列表是否安全。
        """
        return all(chain.is_safe for chain in self.values)


Chainable = Union[MessageChain, I18NMessageChain, PlatformMessageChain,
                  str, list[MessageElement], MessageElement, MessageNodes]


def get_message_chain(session: SessionInfo, chain: Chainable) -> MessageChain:
    if isinstance(chain, PlatformMessageChain):
        chain = chain.values.get(session.target_from, chain.values.get("default", MessageChain.assign("")))
    if isinstance(chain, I18NMessageChain):
        chain = chain.values.get(session.locale.locale, chain.values.get("default", MessageChain.assign("")))
    if isinstance(chain, (str, list, MessageElement)):
        chain = MessageChain.assign(chain)

    if isinstance(chain, (MessageChain, MessageNodes)):
        return chain

    raise TypeError(
        f"Unsupported chain type: {
            type(chain).__name__}, expected MessageChain, MessageNodes, I18NMessageChain, or PlatformMessageChain.")


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
                 disable_joke: bool = False) -> MessageChain:
    split_all = _extract_kecode_blocks(text)
    split_all = [x for x in split_all if x]
    elements = MessageChain.assign()

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
                            img.headers = orjson.loads(str(base64.b64decode(ma.group(2)), "UTF-8"))
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


def convert_senderid_to_atcode(text: str, sender_prefix: str) -> str:
    sender_prefix = sender_prefix.replace("|", "\\|")

    return re.sub(rf"(?<!<AT:)(?<!<@:){sender_prefix}\|\w+", r"<AT:\g<0>>", text).replace("\\", "")


add_export(MessageChain)
add_export(I18NMessageChain)

converter.register_unstructure_hook(Union[MessageChain, I18NMessageChain],
                                    lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)})

converter.register_unstructure_hook(Union[MessageChain, MessageNodes],
                                    lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)})

converter.register_structure_hook(
    Union[MessageChain, I18NMessageChain],
    lambda o, _: converter.structure(o, MessageChain if o["_type"] == "MessageChain" else I18NMessageChain)
)

converter.register_structure_hook(
    Union[MessageChain, MessageNodes],
    lambda o, _: converter.structure(o, MessageChain if o["_type"] == "MessageChain" else MessageNodes)
)

__all__ = [
    "MessageChain",
    "I18NMessageChain",
    "PlatformMessageChain",
    "Chainable",
    "get_message_chain",
    "MessageNodes",
    "match_kecode"]
