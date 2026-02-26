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

MultimodalElement = PlainElement | ImageElement | VoiceElement | RawElement
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
