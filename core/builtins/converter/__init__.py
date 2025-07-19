from datetime import timedelta

from cattrs import Converter

import core.builtins.message.elements as elements
from core.builtins.types import MessageElement
from core.database.models import TargetInfo, SenderInfo
from core.i18n import Locale

converter = Converter()

converter.register_unstructure_hook(MessageElement,
                                    lambda obj: {"_type": type(obj).__name__, **converter.unstructure(obj)})

converter.register_unstructure_hook(TargetInfo,
                                    lambda obj: {"_type": type(obj).__name__, "target_id": obj.target_id})

converter.register_unstructure_hook(SenderInfo,
                                    lambda obj: {"_type": type(obj).__name__, "sender_id": obj.sender_id})

converter.register_unstructure_hook(Locale,
                                    lambda obj: {"_type": "Locale", "locale": obj.locale})

converter.register_unstructure_hook(timedelta,
                                    lambda obj: {"_type": "timedelta", "seconds": obj.total_seconds()})

converter.register_structure_hook(
    MessageElement,
    lambda o, _: converter.structure(o, getattr(elements, o["_type"]))
)

converter.register_structure_hook(
    TargetInfo,
    lambda o, _: TargetInfo)

converter.register_structure_hook(
    SenderInfo,
    lambda o, _: SenderInfo)

converter.register_structure_hook(
    Locale,
    lambda o, _: Locale(o["locale"])
)

converter.register_structure_hook(timedelta,
                                  lambda o, _: timedelta(seconds=o["seconds"]))

__all__ = ["converter"]
