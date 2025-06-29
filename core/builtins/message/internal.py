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
