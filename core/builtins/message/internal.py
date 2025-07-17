from core.exports import add_export
from .elements import *

Plain = plain = PlainElement.assign
Image = image = ImageElement.assign
Voice = voice = VoiceElement.assign
Embed = embed = EmbedElement.assign
EmbedField = embed_field = EmbedFieldElement.assign
Url = url = URLElement.assign
FormattedTime = formatted_time = FormattedTimeElement.assign
I18NContext = i18n_context = I18NContextElement.assign
Mention = mention = MentionElement.assign

add_export(Plain)
add_export(Image)
add_export(Voice)
add_export(Embed)
add_export(EmbedField)
add_export(Url)
add_export(FormattedTime)
add_export(I18NContext)
add_export(Mention)
add_export(plain)
add_export(image)
add_export(voice)
add_export(embed)
add_export(embed_field)
add_export(url)
add_export(formatted_time)
add_export(i18n_context)
add_export(mention)

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
    "plain",
    "image",
    "voice",
    "embed",
    "embed_field",
    "url",
    "formatted_time",
    "i18n_context",
    "mention",
]
