from core.builtins.message.elements import (PlainElement, URLElement, FormattedTimeElement, I18NContextElement,
                                            ImageElement, VoiceElement, EmbedFieldElement, EmbedElement, MentionElement)
from typing import Union


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
