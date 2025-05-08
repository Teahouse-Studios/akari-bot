from cattrs import Converter

from core.builtins.types import MessageElement

import core.builtins.message.elements as elements


converter = Converter()

converter.register_unstructure_hook(MessageElement,
                                    lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)})

converter.register_structure_hook(
    MessageElement,
    lambda o, _: converter.structure(o, getattr(elements, o["_type"]))
)

__all__ = ["converter"]
