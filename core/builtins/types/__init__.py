"""消息元素类型定义模块。"""

from core.builtins.message.elements import (
    PlainElement,
    MarkdownElement,
    URLElement,
    FormattedTimeElement,
    I18NContextElement,
    ImageElement,
    AudioElement,
    VideoElement,
    EmbedFieldElement,
    EmbedElement,
    MentionElement,
    ActionTextElement,
    ButtonElement,
    ButtonFrameElement,
    RawElement,
)

from typing import Union

# 多媒体元素类型联合体 - 包含纯文本、图片、语音、原始格式消息
MultimediaElement = Union[PlainElement, MarkdownElement, ImageElement, AudioElement, VideoElement, RawElement]

# 完整的消息元素类型联合体 - 包含所有支持的消息元素类型
MessageElement = Union[
    MultimediaElement,
    URLElement,
    FormattedTimeElement,
    I18NContextElement,
    EmbedFieldElement,
    EmbedElement,
    MentionElement,
    ActionTextElement,
    ButtonElement,
    ButtonFrameElement,
    None,
]

__all__ = ["MessageElement", "MultimediaElement"]
