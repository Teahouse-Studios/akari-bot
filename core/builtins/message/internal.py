from .elements import *


Plain = plain = PlainElement.assign
Image = image = ImageElement.assign
Voice = voice = VoiceElement.assign
Embed = embed = EmbedElement.assign
EmbedField = embed_field = EmbedFieldElement.assign
Url = url = URLElement.assign
ErrorMessage = error_message = ErrorMessageElement.assign
FormattedTime = formatted_time = FormattedTimeElement.assign
I18NContext = i18n_context = I18NContextElement.assign

__all__ = [
    "Plain",
    "Image",
    "Voice",
    "Embed",
    "EmbedField",
    "Url",
    "ErrorMessage",
    "FormattedTime",
    "I18NContext",
    "plain",
    "image",
    "voice",
    "embed",
    "embed_field",
    "url",
    "error_message",
    "formatted_time",
    "i18n_context",
]
