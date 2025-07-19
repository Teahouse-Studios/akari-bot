from typing import Union

from core.builtins.message.elements import (PlainElement, URLElement, FormattedTimeElement, I18NContextElement,
                                            ImageElement, VoiceElement, EmbedFieldElement, EmbedElement, MentionElement)

MessageElement = Union[
    PlainElement,
    URLElement,
    FormattedTimeElement,
    I18NContextElement,
    ImageElement,
    VoiceElement,
    EmbedFieldElement,
    EmbedElement,
    MentionElement,
]

__all__ = [MessageElement]
