"""消息内部接口模块 - 为消息元素提供便利的别名和导出。"""

from .elements import *


Plain = plain = PlainElement.assign

Markdown = markdown = MarkdownElement.assign

Image = image = ImageElement.assign

Audio = audio = AudioElement.assign

Video = video = VideoElement.assign

Embed = embed = EmbedElement.assign

EmbedField = embed_field = EmbedFieldElement.assign

Url = url = URLElement.assign

FormattedTime = formatted_time = FormattedTimeElement.assign

I18NContext = i18n_context = I18NContextElement.assign

Mention = mention = MentionElement.assign

Raw = raw = RawElement.assign

ActionText = action_text = ActionTextElement.assign

Button = button = ButtonElement.assign

ButtonFrame = button_frame = ButtonFrameElement.assign

__all__ = [
    "Plain",
    "Markdown",
    "Image",
    "Audio",
    "Embed",
    "EmbedField",
    "Url",
    "FormattedTime",
    "I18NContext",
    "Mention",
    "Raw",
    "ActionText",
    "Button",
    "ButtonPermission",
    "ButtonRows",
    "ButtonFrame",
    "plain",
    "markdown",
    "image",
    "audio",
    "embed",
    "embed_field",
    "url",
    "formatted_time",
    "i18n_context",
    "mention",
    "raw",
    "action_text",
    "button",
    "button_frame",
]
