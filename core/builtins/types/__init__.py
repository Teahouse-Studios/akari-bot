from core.builtins.message.elements import (PlainElement, URLElement, FormattedTimeElement, I18NContextElement,
                                            ImageElement, VoiceElement, EmbedFieldElement, EmbedElement, MentionElement,
                                            RawElement)

MessageElement = PlainElement | URLElement | FormattedTimeElement | I18NContextElement | ImageElement | VoiceElement | EmbedFieldElement | EmbedElement | MentionElement | RawElement

__all__ = ["MessageElement"]
