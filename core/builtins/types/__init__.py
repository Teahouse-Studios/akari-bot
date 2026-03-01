"""
消息元素类型定义模块。

定义了系统中所有支持的消息元素类型和类型联合体，
用于类型注解和类型检查。
"""

from core.builtins.message.elements import (
    PlainElement,
    URLElement,
    FormattedTimeElement,
    I18NContextElement,
    ImageElement,
    VoiceElement,
    EmbedFieldElement,
    EmbedElement,
    MentionElement,
    RawElement,
)

# 多媒体元素类型联合体 - 包含纯文本、图片、语音、原始格式消息
MultimodalElement = PlainElement | ImageElement | VoiceElement | RawElement

# 完整的消息元素类型联合体 - 包含所有支持的消息元素类型
MessageElement = (
    MultimodalElement
    | URLElement
    | FormattedTimeElement
    | I18NContextElement
    | EmbedFieldElement
    | EmbedElement
    | MentionElement
)

__all__ = ["MessageElement", "MultimodalElement"]
