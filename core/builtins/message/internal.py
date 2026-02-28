"""
消息内部接口模块 - 为消息元素提供便利的别名和导出。

该模块为各种消息元素类提供了简洁的别名（小写形式），
使得在代码中可以方便地使用这些元素，并将其导出供系统使用。
"""

from core.exports import add_export
from .elements import *

# ========== 消息元素别名定义 ==========
# 每个元素都提供大写和小写两种形式的别名

# 纯文本元素 - 用于发送简单的文本消息
Plain = plain = PlainElement.assign

# 图片元素 - 用于发送图片消息
Image = image = ImageElement.assign

# 语音元素 - 用于发送语音消息
Voice = voice = VoiceElement.assign

# 嵌入式内容元素 - 用于发送卡片、富文本等嵌入式内容
Embed = embed = EmbedElement.assign

# 嵌入式内容字段元素 - 用于构建嵌入式内容的字段
EmbedField = embed_field = EmbedFieldElement.assign

# URL 链接元素 - 用于发送链接
Url = url = URLElement.assign

# 格式化时间元素 - 用于发送带有日期/时间格式化的消息
FormattedTime = formatted_time = FormattedTimeElement.assign

# 国际化上下文元素 - 用于发送支持多语言的消息（会自动根据语言选择对应的文本）
I18NContext = i18n_context = I18NContextElement.assign

# 提及用户元素 - 用于在消息中提及（@）指定用户
Mention = mention = MentionElement.assign

# 原始格式元素 - 用于发送原始格式的消息内容
Raw = raw = RawElement.assign

# ========== 导出所有别名 ==========
# 将别名导出到系统的导出列表中，供其他模块使用

add_export(Plain)
add_export(Image)
add_export(Voice)
add_export(Embed)
add_export(EmbedField)
add_export(Url)
add_export(FormattedTime)
add_export(I18NContext)
add_export(Mention)
add_export(Raw)
add_export(plain)
add_export(image)
add_export(voice)
add_export(embed)
add_export(embed_field)
add_export(url)
add_export(formatted_time)
add_export(i18n_context)
add_export(mention)
add_export(raw)

__all__ = [
    "Plain",
    "Image",
    "Voice",
    "Embed",
    "EmbedField",
    "Url",
    "FormattedTime",
    "I18NContext",
    "Mention",
    "Raw",
    "plain",
    "image",
    "voice",
    "embed",
    "embed_field",
    "url",
    "formatted_time",
    "i18n_context",
    "mention",
    "raw",
]
