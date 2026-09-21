"""消息链模块 - 实现消息链的核心数据结构和处理逻辑。"""

from __future__ import annotations

import base64
import html
import random
import re
from attrs import define
from copy import deepcopy
from typing import Any, TYPE_CHECKING
from urllib.parse import unquote, urlparse

import orjson

from core.builtins.types import MessageElement
from core.builtins.converter import converter
from core.builtins.message.elements import (
    BaseElement,
    PlainElement,
    MarkdownElement,
    EmbedElement,
    FormattedTimeElement,
    I18NContextElement,
    URLElement,
    ImageElement,
    AudioElement,
    VideoElement,
    MentionElement,
    ActionTextElement,
    ButtonPermission,
    ButtonElement,
    ButtonRows,
    ButtonFrameElement,
    RawElement,
)
from core.config.base import BaseConfig
from core.constants import Secret
from core.exports import add_export
from core.i18n import Locale
from core.utils.joke import shuffle_joke as joke
from core.logger import Logger
from core.utils.func import convert_bool
from core.utils.http import url_pattern
from core.utils.url_audit import GlobalURLBlocklist, evaluate_url_policy, redact_blocklisted_urls
from core.utils.button import AUTO_BUTTON_MAX_ROWS, AUTO_BUTTONS_PER_ROW

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.internal import MessageSession


_I18N_MESSAGE_PATTERN = re.compile(r"\[AKARI-MSG:([A-Za-z0-9_-]+={0,2})\]")

default_locale = BaseConfig.default_locale


@define
class MessageChain:
    """消息链类 - 表示由多个消息元素组成的完整消息。"""

    values: list[MessageElement]

    @classmethod
    def create(cls):
        """创建一个空的消息链实例。"""

        return cls(values=[])

    @classmethod
    def assign(
        cls,
        elements: str | list[MessageElement] | tuple[MessageElement, ...] | MessageElement | MessageChain | None = None,
    ):
        """创建消息链的工厂方法。

        :param elements: 消息元素或其集合
        :return: 消息链实例（会进行深拷贝）
        """
        if isinstance(elements, MessageChain):
            return elements

        values = []

        if isinstance(elements, str):
            elements = PlainElement.assign(elements)

        if isinstance(elements, BaseElement):
            elements = [elements]

        # 单个字典即 to_list() 产出的一个元素（含 _type 判别键），整体还原为消息元素
        if isinstance(elements, dict):
            elements = [converter.structure(elements, MessageElement)]

        if isinstance(elements, (list, tuple)):
            for e in elements:
                if e is None:
                    continue
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

        return deepcopy(cls(values))

    @property
    def is_safe(self) -> bool:
        """检查消息链是否包含安全内容。

        :return: 如果消息链不包含敏感信息返回 True，否则返回 False
        """

        def unsafeprompt(name, secret, text):
            return f'{name} contains unsafe text "{secret}": {text}'

        def check_text(name: str, text: Any) -> bool:
            if text is None:
                return True
            if secret := Secret.check(str(text)):
                Logger.warning(unsafeprompt(name, secret, text))
                return False
            return True

        def check_value(name: str, value: Any) -> bool:
            if isinstance(value, (MessageChain, MessageNodes)):
                return value.is_safe
            if isinstance(value, BaseElement):
                # 复用元素所在链的检查逻辑，避免为每种嵌套元素重复实现分支
                return MessageChain.assign(value).is_safe
            return check_text(name, value)

        for v in self.values:
            if isinstance(v, PlainElement):
                if not check_text("Plain", v.text):
                    return False
            elif isinstance(v, URLElement):
                if not check_text("URL", v.original_url):
                    return False
            elif isinstance(v, EmbedElement):
                if not check_text("Embed.title", v.title):
                    return False
                if not check_text("Embed.description", v.description):
                    return False
                if not check_text("Embed.footer", v.footer):
                    return False
                if not check_text("Embed.author", v.author):
                    return False
                if not check_text("Embed.url", v.url):
                    return False
                if v.fields:
                    for f in v.fields:
                        if not check_text("Embed.field.name", f.name):
                            return False
                        if not check_text("Embed.field.value", f.value):
                            return False
            # 参数会在客户端发送阶段才代入文案，服务端的链检查必须提前覆盖
            elif isinstance(v, I18NContextElement):
                for key, value in v.kwargs.items():
                    if not check_value(f"I18NContext.{key}", value):
                        return False
            elif isinstance(v, ActionTextElement):
                if not check_value("ActionText.text", v.text):
                    return False
                if not check_value("ActionText.show", v.show):
                    return False
            elif isinstance(v, ButtonElement):
                if not check_text("Button.show", v.show):
                    return False
            elif isinstance(v, ButtonFrameElement):
                for row in v.rows:
                    for button in row.buttons:
                        if not check_text("Button.show", button.show):
                            return False
            elif isinstance(v, RawElement):
                if not check_text("Raw", v.value):
                    return False

        return True

    def as_sendable(
        self,
        session_info: SessionInfo | MessageSession | None = None,
        parse_message: bool = True,
        enable_markdown: bool = True,
    ) -> MessageChain:
        """将消息链转换为可发送的格式。

        :param session_info: 会话信息，用于本地化和平台特定的处理
        :param parse_message: 是否解析消息中的特殊格式（如 KE 码、多语言标记等）
        :param enable_markdown: 是否启用 markdown 格式转换
        :return: 可发送的消息元素列表
        """
        value = []
        support_embed = True

        if session_info:
            # 传入 MessageSession 时取出其 session_info；SessionInfo 自身没有该属性，原样返回。
            # 不经 exports 判类型，以免受注册时机影响。
            session_info = getattr(session_info, "session_info", session_info)

            support_embed = session_info.support_embed

        def append_parsed_elements(element_chain: MessageChain) -> None:
            inline_pending = False
            for elem in element_chain.values:
                elem_ = (
                    MessageChain.assign(elem)
                    .as_sendable(session_info, parse_message=False, enable_markdown=enable_markdown)
                    .values
                )
                is_action_text = isinstance(elem, ActionTextElement)
                for el in elem_:
                    # 该赋值原本假定 elem 是纯文本元素，指令操作降级后
                    # elem_ 中也会出现纯文本，不加判定会把元素改写为字符串
                    if isinstance(el, PlainElement) and isinstance(elem, PlainElement) and session_info:
                        elem.text = session_info.locale.t_str(el.text)
                for el in elem_:
                    if (is_action_text or inline_pending) and isinstance(el, PlainElement):
                        _append_inline(value, el)
                    else:
                        value.append(el)
                inline_pending = is_action_text

        for x in self.values:
            if x is None:
                continue

            if isinstance(x, EmbedElement) and GlobalURLBlocklist.rules():
                x = deepcopy(x)
                locale = session_info.locale if session_info else Locale(default_locale)
                replacement = locale.t("message.url.blocked")
                for attribute in ("title", "description", "author", "footer"):
                    text = getattr(x, attribute)
                    if text:
                        translated = locale.t_str(text)
                        setattr(x, attribute, redact_blocklisted_urls(translated, replacement))
                fields = x.fields if isinstance(x.fields, list) else [x.fields] if x.fields else []
                for field in fields:
                    field.name = redact_blocklisted_urls(locale.t_str(field.name), replacement)
                    field.value = redact_blocklisted_urls(locale.t_str(field.value), replacement)
                if x.url and GlobalURLBlocklist.is_blocked(x.url):
                    x.url = None

            if isinstance(x, EmbedElement) and not support_embed:
                value += x.to_message_chain(session_info)

            elif isinstance(x, MarkdownElement):
                markdown_enabled = enable_markdown and (session_info is None or session_info.support_markdown)
                source = PlainElement.assign(x.text, disable_joke=x.disable_joke, allow_parse=x.allow_parse)
                converted = MessageChain.assign(source).as_sendable(
                    session_info,
                    parse_message=parse_message,
                    enable_markdown=enable_markdown,
                )
                for element in converted:
                    if isinstance(element, PlainElement):
                        value.append(
                            MarkdownElement.assign(
                                element.text,
                                disable_joke=element.disable_joke,
                                allow_parse=element.allow_parse,
                            )
                            if markdown_enabled
                            else MarkdownElement.assign(
                                element.text,
                                disable_joke=element.disable_joke,
                                allow_parse=element.allow_parse,
                            ).to_plain()
                        )
                    else:
                        value.append(element)

            elif isinstance(x, PlainElement):
                if session_info:
                    if x.text != "":
                        if parse_message and x.allow_parse:
                            x.text = session_info.locale.t_str(x.text)
                            element_chain = match_kecode(x.text, x.disable_joke)
                            # 指令操作是行内元素：它自身的产物、以及紧随其后的纯文本，
                            # 都须并入上一行，否则同出一个字符串的一句话会被平台的
                            # 换行拼接拆成数行。其余元素照旧各自追加，以免破坏
                            # MessageChain([Plain("a"), Plain("b")]) 经 KE 码往返后
                            # 仍应是两个元素的既有约定。
                            append_parsed_elements(element_chain)
                            continue
                    else:
                        x = PlainElement.assign(session_info.locale.t("error.message.chain.empty"))
                locale = session_info.locale if session_info else Locale(default_locale)
                x.text = redact_blocklisted_urls(x.text, locale.t("message.url.blocked"))
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
                    if isinstance(v, MessageChain):
                        # Template.safe_substitute 会把参数强制转成字符串，因此先将消息链
                        # 结构化并编码成可嵌入模板的内部标记，翻译后再还原。
                        x.kwargs[k] = _serialize_i18n_message(v)
                    if isinstance(v, ActionTextElement):
                        # 指令操作同样需要保留元素类型；先解析内层多语言元素再序列化。
                        x.kwargs[k] = _serialize_i18n_message(v.resolve(session_info))

                t_value = locale.t(x.key, x.fallback, x.locale_failed_prompt, **x.kwargs)
                append_parsed_elements(_deserialize_i18n_messages(t_value, x.disable_joke))

            elif isinstance(x, URLElement):
                url_policy = evaluate_url_policy(x.original_url)
                if url_policy.blocked:
                    locale = session_info.locale if session_info else Locale(default_locale)
                    value.append(PlainElement.assign(locale.t("message.url.blocked"), disable_joke=True))
                    continue

                globally_trusted = bool(
                    session_info and session_info.use_url_manager and x.trusted is None and url_policy.allowed
                )
                # 链接须按未认证处理的两种来源：模块显式标记为不可信，或未表态而会话启用了 URLManager
                needs_guard = bool(
                    session_info
                    and not globally_trusted
                    and x.trusted is not True
                    and (x.trusted is False or session_info.use_url_manager)
                )
                if needs_guard and session_info.support_markdown and enable_markdown:
                    title = session_info.locale.t("message.url.untrusted")
                    value.append(PlainElement.assign(f"```{title}\n{x.original_url}\n```", disable_joke=True))
                    continue

                if session_info and x.trusted is None and not globally_trusted and session_info.use_url_manager:
                    x = URLElement.assign(x.url, trusted=False, md_format_name=x.md_format_name)
                if session_info and (session_info.use_url_md_format and not x.applied_md_format) and enable_markdown:
                    x = URLElement.assign(x.url, md_format=True, md_format_name=x.md_format_name)

                value.append(PlainElement.assign(x.url, disable_joke=True))

            elif isinstance(x, ActionTextElement):
                # 内层的多语言元素只有在此处才能确定会话语言，故转换阶段一次性解析
                x = x.resolve(session_info)
                if session_info and session_info.support_action_text and enable_markdown and x.text.text:
                    value.append(x)
                else:
                    _append_inline(value, x.to_plain(session_info))

            elif isinstance(x, ButtonElement):
                if not session_info or session_info.support_button:
                    value.append(x)

            elif isinstance(x, ButtonFrameElement):
                if not session_info or session_info.support_button:
                    value.append(x)

            else:
                value.append(x)

        buttons = [x for x in value if isinstance(x, ButtonElement)]
        if buttons:
            capacity = AUTO_BUTTONS_PER_ROW * AUTO_BUTTON_MAX_ROWS
            if len(buttons) > capacity:
                Logger.warning(
                    f"Got {len(buttons)} standalone buttons but only {capacity} fit; "
                    f"dropped the last {len(buttons) - capacity}."
                )
                buttons = buttons[:capacity]
            value = [x for x in value if not isinstance(x, ButtonElement)]
            rows = [
                ButtonRows.assign(buttons[start : start + AUTO_BUTTONS_PER_ROW])
                for start in range(0, len(buttons), AUTO_BUTTONS_PER_ROW)
            ]
            value.append(ButtonFrameElement.assign(rows))

        if not value:
            if session_info:
                value.append(PlainElement.assign(session_info.locale.t("error.message.chain.empty")))

        for x in value:
            if isinstance(x, PlainElement) and not x.disable_joke:
                x.text = joke(x.text)

        return MessageChain.assign(value)

    def to_str(
        self, text_only=True, element_filter: tuple[MessageElement, ...] | None = None, connector: str = "\n"
    ) -> str:
        """将消息链转换为字符串。

        :param text_only: 是否仅转换文本元素为字符串，默认为 True
                         True: 只包含 PlainElement 的文本内容
                         False: 包含所有元素的字符串表示
        :param element_filter: 可选的元素过滤器，指定哪些元素类型需要被转换为字符串
                              如 (PlainElement, ImageElement) 只转换这两种类型
        :param connector: 元素之间的连接符，默认为换行符 "\n"
        :return: 转换后的字符串
        """
        result = []
        for x in self.values:
            if element_filter and not isinstance(x, element_filter):
                continue

            if isinstance(x, PlainElement):
                result.append(x.text)
            else:
                if not text_only:
                    result.append(str(x))

        return connector.join(result)

    def to_list(self) -> list[dict[str, Any]]:
        """将消息链序列化为列表。

        :return: 字典列表，每个字典代表一个消息元素
        """
        return [converter.unstructure(x, MessageElement) for x in self.values if x is not None]

    def to_kecode(self) -> str:
        _t = ""
        for x in self.values:
            _t += x.kecode()
        return _t

    @classmethod
    def from_list(cls, lst: list) -> MessageChain:
        """从列表构造消息链。

        :param lst: 消息元素的字典列表
        :return: 新的消息链实例
        """
        # 列表中每一项都是一个完整的元素字典，须整体交给 converter 还原，
        # 逐键遍历只会把键名当作元素传入
        converted = [converter.structure(x, MessageElement) for x in lst]
        return deepcopy(cls(converted))

    @staticmethod
    def _normalize(element):
        if element is None:
            return None
        if isinstance(element, str):
            return PlainElement.assign(element) if element else None
        if isinstance(element, BaseElement):
            return element
        Logger.error(f"Unexpected message type: {element}")
        return None

    def append(self, element):
        """添加一个消息元素到消息链末尾。

        :param element: 要添加的消息元素
        """
        normalized = self._normalize(element)
        if normalized is not None:
            self.values.append(normalized)

    def remove(self, element):
        """从消息链中删除一个消息元素。

        :param element: 要删除的消息元素
        """
        self.values.remove(element)

    def insert(self, index, element):
        """在指定位置插入一个消息元素。

        :param index: 插入位置的索引
        :param element: 要插入的消息元素
        """
        normalized = self._normalize(element)
        if normalized is not None:
            self.values.insert(index, normalized)

    def copy(self):
        """复制消息链。

        :return: 新的消息链实例
        """
        return MessageChain.assign(self.values.copy())

    def contains(self, types: type[MessageElement] | tuple[MessageElement]) -> bool:
        return any(isinstance(x, types) for x in self.values)

    def only(self, types: type[MessageElement] | tuple[MessageElement]) -> bool:
        return all(isinstance(x, types) for x in self.values)

    def extend(self, other: MessageChain):
        return self.__iadd__(other)

    def __str__(self):
        """返回消息链的字符串表示（用于调试）"""
        return f"[{', '.join([x.__repr__() for x in self.values])}]"

    def __iter__(self):
        """使消息链可迭代"""
        return iter(self.values)

    def __len__(self):
        """返回消息链中元素的数量"""
        return len(self.values)

    def __add__(self, other):
        """消息链的加法操作。

        :param other: 另一个消息链或元素列表
        :return: 新的消息链
        :raises TypeError: 如果操作数类型不支持
        """
        if isinstance(other, MessageChain):
            return MessageChain.assign(self.values + other.values)
        if isinstance(other, list):
            return MessageChain.assign(self.values + other)
        if isinstance(other, MessageElement):
            return MessageChain.assign(self.values + [other])
        raise TypeError(f'Unsupported operand type(s) for +: "MessageChain" and "{type(other).__name__}"')

    def __radd__(self, other):
        """
        消息链的右加法操作（当左操作数不支持加法时调用）。

        :param other: 另一个消息链或元素列表
        :return: 新的消息链
        :raises TypeError: 如果操作数类型不支持
        """
        if isinstance(other, MessageChain):
            return MessageChain.assign(other.values + self.values)
        if isinstance(other, list):
            return MessageChain.assign(other + self.values)
        if isinstance(other, MessageElement):
            return MessageChain.assign(self.values + [other])
        raise TypeError(f'Unsupported operand type(s) for +: "{type(other).__name__}" and "MessageChain"')

    def __iadd__(self, other):
        """消息链的原地加法操作（+=）。

        :param other: 另一个消息链或元素列表
        :return: 修改后的消息链自身
        :raises TypeError: 如果操作数类型不支持
        """
        if isinstance(other, MessageChain):
            self.values += other.values
        elif isinstance(other, list):
            # 列表中的裸字符串一并归一化，与 assign() 的行为保持一致
            self.values += [e for e in (self._normalize(x) for x in other) if e is not None]
        elif isinstance(other, MessageElement):
            self.values += [other]
        else:
            raise TypeError(f'Unsupported operand type(s) for +=: "MessageChain" and "{type(other).__name__}"')
        return self

    def __contains__(self, item):
        for x in self.values:
            if isinstance(x, item):
                return True
        return False


@define
class I18NMessageChain:
    """多语言消息链 - 用于处理不同语言环境下的消息。"""

    values: dict[str, MessageChain]

    @classmethod
    def assign(cls, values: dict[str, MessageChain]) -> I18NMessageChain:
        """创建多语言消息链的工厂方法。

        :param values: 多语言消息链元素，键为语言代码，值为消息链
                      必须包含 `default` 键用于回滚处理
        :return: I18NMessageChain 实例
        :raises TypeError: 如果 values 不是字典
        :raises ValueError: 如果缺少 "default" 键
        """
        if not isinstance(values, dict):
            raise TypeError("I18NMessageChain values must be a dictionary.")
        if "default" not in values:
            raise ValueError('I18NMessageChain values must have "default" key.')
        return cls(values=deepcopy(values))


@define
class PlatformMessageChain:
    """平台消息链 - 用于处理不同平台的消息。"""

    values: dict[str, MessageChain | I18NMessageChain]

    @classmethod
    def assign(cls, values: dict[str, MessageChain | I18NMessageChain]) -> PlatformMessageChain:
        """创建平台消息链的工厂方法。

        :param values: 平台消息链元素，键为平台名称，值为消息链
                      必须包含 `default` 键用于回滚处理
        :return: PlatformMessageChain 实例
        :raises TypeError: 如果 values 不是字典
        """
        if not isinstance(values, dict):
            raise TypeError("PlatformMessageChain values must be a dictionary.")
        return cls(values=deepcopy(values))


@define
class MessageNodes:
    """消息节点列表 - 用于表示转发消息。"""

    values: list[MessageChain]
    name: str = ""

    @classmethod
    def assign(cls, values: list[MessageChain], name: str | None = None):
        """创建消息节点列表的工厂方法。

        :param values: 消息链列表，每个消息链作为一个节点
        :param name: 节点列表的名称，默认为随机生成的字符串
        :return: MessageNodes 实例
        """
        if not name:
            name = "Message " + "".join(random.sample("abcdefghijklmnopqrstuvwxyz", 5))

        return cls(values=values, name=name)

    @property
    def is_safe(self) -> bool:
        """检查消息节点列表是否安全。

        :return: 如果所有节点都安全返回 True，否则返回 False
        """
        return all(chain.is_safe for chain in self.values)


# 可作为消息发送的入参类型。仅用于约束参数，不存在输入与输出的类型绑定，
# 故取联合类型而非 TypeVar：后者是取值受限的类型变量，会拒绝 MessageChain | MessageNodes
# 这类联合，使 get_message_chain() 的结果无法回传给 send_message()。
Chainable = (
    MessageChain
    | I18NMessageChain
    | PlatformMessageChain
    | str
    | list[str]
    | list[MessageElement]
    | MessageElement
    | MessageNodes
)


def get_message_chain(session: SessionInfo, chain: Chainable) -> MessageChain | MessageNodes:
    """根据会话信息获取合适的消息链。

    :param session: 会话信息，包含平台、语言等配置
    :param chain: 可链接的消息对象（支持多种类型）
    :return: 处理后的 MessageChain 实例；传入合并转发消息时原样返回 MessageNodes
    :raises TypeError: 如果传入不支持的链类型
    """
    # 本函数的职责即是把多种入参归一化，过程中类型会逐步收敛，故以 Any 承接
    resolved: Any = chain

    if isinstance(resolved, PlatformMessageChain):
        resolved = resolved.values.get(session.target_from, resolved.values.get("default", MessageChain.assign("")))

    if isinstance(resolved, I18NMessageChain):
        resolved = resolved.values.get(session.locale.locale, resolved.values.get("default", MessageChain.assign("")))

    if isinstance(resolved, (str, list, MessageElement)):
        resolved = MessageChain.assign(resolved)

    if isinstance(resolved, (MessageChain, MessageNodes)):
        return resolved

    raise TypeError(
        f"Unsupported chain type: {
            type(resolved).__name__
        }, expected MessageChain, MessageNodes, I18NMessageChain, or PlatformMessageChain."
    )


def _extract_kecode_blocks(text):
    result = []
    i = 0
    while i < len(text):
        if text.startswith("[KE:", i):
            start = i
            i += 4
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


def _append_inline(value: list, element: PlainElement) -> None:
    if value and isinstance(value[-1], PlainElement):
        value[-1].text += element.text
    else:
        value.append(element)


def _serialize_i18n_message(value: MessageChain | MessageElement) -> str:
    chain = value if isinstance(value, MessageChain) else MessageChain.assign(value)
    payload = orjson.dumps(converter.unstructure(chain, MessageChain))
    encoded = base64.urlsafe_b64encode(payload).decode("ascii")
    return f"[AKARI-MSG:{encoded}]"


def _deserialize_i18n_messages(text: str, disable_joke: bool = False) -> MessageChain:
    elements = MessageChain.create()
    cursor = 0

    for match in _I18N_MESSAGE_PATTERN.finditer(text):
        if prefix := text[cursor : match.start()]:
            elements.extend(match_kecode(prefix, disable_joke))

        try:
            payload = base64.urlsafe_b64decode(match.group(1))
            elements.extend(converter.structure(orjson.loads(payload), MessageChain))
        except Exception:
            elements.extend(match_kecode(match.group(0), disable_joke))

        cursor = match.end()

    if suffix := text[cursor:]:
        elements.extend(match_kecode(suffix, disable_joke))

    return elements


def match_kecode(text: str, disable_joke: bool = False) -> MessageChain:
    """解析 KE 码格式的文本并转换为消息链。

    :param text: 包含 KE 码的文本字符串
    :param disable_joke: 是否禁用玩笑功能（默认为 False）
    :return: 解析后的消息链
    """
    split_all = _extract_kecode_blocks(text)
    split_all = [x for x in split_all if x]

    elements = MessageChain.assign()

    for e in split_all:
        match = re.match(r"\[KE:([^\s,\]]+)(?:,(.*))?\]$", e, re.DOTALL)

        if not match:
            if e != "":
                elements.append(PlainElement.assign(e, disable_joke=disable_joke))
            continue

        try:
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

            parsed_params = {}

            for a in params:
                ma = re.match(r"(.*?)=(.*)", a, re.DOTALL)

                if ma:
                    key = ma.group(1).strip()
                    value = html.unescape(ma.group(2))

                    parsed_params[key] = value

            if element_type == "plain":
                # 写入侧已 urlencode，此处解码还原。手写的 KE 码不含百分号转义时，
                # 解码为恒等变换，故不影响既有的手写用法
                text_value = unquote(parsed_params.get("text", ""))

                local_disable_joke = convert_bool(parsed_params.get("disable_joke"), disable_joke)
                allow_parse = convert_bool(parsed_params.get("allow_parse"), True)

                elements.append(
                    PlainElement.assign(text_value, disable_joke=local_disable_joke, allow_parse=allow_parse)
                )

            elif element_type == "markdown":
                text_value = unquote(parsed_params.get("text", ""))
                local_disable_joke = convert_bool(parsed_params.get("disable_joke"), disable_joke)
                allow_parse = convert_bool(parsed_params.get("allow_parse"), True)
                elements.append(
                    MarkdownElement.assign(text_value, disable_joke=local_disable_joke, allow_parse=allow_parse)
                )

            elif element_type == "image":
                path = parsed_params.get("path")

                if path:
                    parse_url = urlparse(path)

                    if parse_url[0] == "file" or url_pattern.match(parse_url[1]):
                        max_h = parsed_params.get("max_h")
                        allow_split = convert_bool(parsed_params.get("allow_split"), True)
                        img = ImageElement.assign(
                            path=path,
                            max_h=int(max_h) if max_h and max_h.isdigit() else None,
                            allow_split=allow_split,
                        )

                        headers = parsed_params.get("headers")

                        if headers:
                            img.headers = orjson.loads(str(base64.b64decode(headers), "UTF-8"))

                        elements.append(img)
                    else:
                        max_h = parsed_params.get("max_h")
                        allow_split = convert_bool(parsed_params.get("allow_split"), True)
                        elements.append(
                            ImageElement.assign(
                                path,
                                max_h=int(max_h) if max_h and max_h.isdigit() else None,
                                allow_split=allow_split,
                            )
                        )

            elif element_type == "audio":
                path = parsed_params.get("path")

                if path:
                    elements.append(AudioElement.assign(path))

            elif element_type == "video":
                path = parsed_params.get("path")

                if path:
                    elements.append(VideoElement.assign(path))

            elif element_type == "i18n":
                i18nkey = parsed_params.get("i18nkey")

                if i18nkey:
                    local_disable_joke = convert_bool(parsed_params.pop("disable_joke", None), disable_joke)

                    fallback = convert_bool(parsed_params.pop("fallback", None), True)

                    locale_failed_prompt = convert_bool(parsed_params.pop("locale_failed_prompt", None), True)

                    parsed_params.pop("i18nkey", None)

                    elements.append(
                        I18NContextElement.assign(
                            i18nkey,
                            disable_joke=local_disable_joke,
                            fallback=fallback,
                            locale_failed_prompt=locale_failed_prompt,
                            **parsed_params,
                        )
                    )

            elif element_type == "mention":
                userid = parsed_params.get("userid")

                if userid:
                    elements.append(MentionElement.assign(userid))
            elif element_type == "url":
                # 不复用形参 text：覆写会污染其后各块的解析
                url_value = parsed_params.get("text")

                if url_value:
                    trusted_param = parsed_params.get("trusted")
                    trusted = None if trusted_param is None else trusted_param == "1"
                    elements.append(URLElement.assign(unquote(url_value), trusted=trusted))

            elif element_type == "action_text":
                action_text_value = parsed_params.get("text")

                if action_text_value:
                    action_show_value = parsed_params.get("show")

                    elements.append(
                        ActionTextElement.assign(
                            unquote(action_text_value),
                            unquote(action_show_value) if action_show_value is not None else None,
                            convert_bool(parsed_params.get("reference"), False),
                            convert_bool(parsed_params.get("show_on_fallback"), True),
                            convert_bool(parsed_params.get("quote_on_fallback"), False),
                        )
                    )

            elif element_type == "button":
                button_show = parsed_params.get("show")
                button_value = parsed_params.get("value")
                if button_show is not None and button_value is not None:
                    button_reply_id = parsed_params.get("reply_id")
                    elements.append(
                        ButtonElement.assign(
                            unquote(button_show),
                            unquote(button_value),
                            unquote(button_reply_id) if button_reply_id is not None else None,
                            ButtonPermission.normalize(parsed_params.get("permission")),
                            int(parsed_params["click_limit"]) if parsed_params.get("click_limit") is not None else 1,
                        )
                    )
                    continue

                # 兼容旧版 ButtonElement 的按行 JSON KE 码。
                button_data = parsed_params.get("data")
                if button_data:
                    decoded = orjson.loads(unquote(button_data))
                    rows = [
                        ButtonRows.assign([ButtonElement.assign(show, value) for show, value in row.items()])
                        for row in decoded
                        if isinstance(row, dict)
                    ]
                    elements.append(ButtonFrameElement.assign(rows))

            elif element_type == "button_frame":
                button_data = parsed_params.get("data")
                if button_data:
                    decoded = orjson.loads(unquote(button_data))
                    rows = [
                        ButtonRows.assign(
                            [
                                ButtonElement.assign(
                                    button["show"],
                                    button["value"],
                                    button.get("reply_id"),
                                    button.get("permission"),
                                    button.get("click_limit", 1),
                                )
                                for button in row
                                if isinstance(button, dict) and "show" in button and "value" in button
                            ]
                        )
                        for row in decoded
                        if isinstance(row, list)
                    ]
                    elements.append(ButtonFrameElement.assign(rows))

        except Exception:
            elements.append(PlainElement.assign(e, disable_joke=disable_joke))
    return elements


def escape_special_char(s: str, escape_comma: bool = True) -> str:
    """
    转义特殊占位符标记的特殊字符。

    :param s: 要转义的字符串。
    :param escape_comma: 是否转义逗号（`,`）。
    :return: 转义后的字符串。
    """
    s = s.replace("&", "&amp;")
    s = s.replace("{", "&#123;").replace("}", "&#124;")
    s = s.replace("[", "&#91;").replace("]", "&#93;")
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    if escape_comma:
        s = s.replace(",", "&#44;")
    return s


add_export(MessageChain)
add_export(I18NMessageChain)


converter.register_unstructure_hook(
    MessageChain | I18NMessageChain, lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)}
)

converter.register_unstructure_hook(
    MessageChain | MessageNodes, lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)}
)

converter.register_structure_hook(
    MessageChain | I18NMessageChain,
    lambda o, _: converter.structure(o, MessageChain if o["_type"] == "MessageChain" else I18NMessageChain),
)

converter.register_structure_hook(
    MessageChain | MessageNodes,
    lambda o, _: converter.structure(o, MessageChain if o["_type"] == "MessageChain" else MessageNodes),
)

__all__ = [
    "MessageChain",
    "I18NMessageChain",
    "PlatformMessageChain",
    "Chainable",
    "get_message_chain",
    "MessageNodes",
    "match_kecode",
    "escape_special_char",
]
