"""类型转换模块 - 提供对象序列化和反序列化的通用机制。"""

from datetime import timedelta

from cattrs import Converter

import core.builtins.message.elements as elements
from core.builtins.message.elements import I18NContextElement
from core.builtins.session.event_types import EventName
from core.builtins.types import MessageElement
from core.database.models import TargetUnionInfo, SenderUnionInfo
from core.i18n import Locale
from core.logger import Logger
from core.exports import exports

converter = Converter()


def elements_to_kwargs(kwargs):
    Logger.trace(f"kwargs before unstructured: {kwargs}")
    for k in kwargs:
        if isinstance(kwargs[k], MessageElement):
            kwargs[k] = {"_type": type(kwargs[k]).__name__, "element": converter.unstructure(kwargs[k])}
            continue
        if msg_chain := exports.get("MessageChain"):
            if isinstance(kwargs[k], msg_chain):
                kwargs[k] = {"_type": type(kwargs[k]).__name__, "element": converter.unstructure(kwargs[k])}
                continue

    Logger.trace(f"kwargs after unstructured: {kwargs}")
    return kwargs


converter.register_unstructure_hook(
    MessageElement,
    lambda obj: {
        "_type": type(obj).__name__,
        **(
            converter.unstructure(obj)
            if not isinstance(obj, I18NContextElement)
            else {"key": obj.key, "disable_joke": obj.disable_joke, "kwargs": elements_to_kwargs(obj.kwargs)}
        ),
    },
)


# 将 TargetUnionInfo 对象转换为字典，由于序列化需要从数据库重新异步获取，只保留 _type 和 union_id 字段
converter.register_unstructure_hook(
    TargetUnionInfo, lambda obj: {"_type": type(obj).__name__, "union_id": obj.union_id}
)

# 将 SenderUnionInfo 对象转换为字典，由于序列化需要从数据库重新异步获取，只保留 _type 和 union_id 字段
converter.register_unstructure_hook(
    SenderUnionInfo, lambda obj: {"_type": type(obj).__name__, "union_id": obj.union_id}
)

converter.register_unstructure_hook(Locale, lambda obj: {"_type": "Locale", "locale": obj.locale})

converter.register_unstructure_hook(timedelta, lambda obj: {"_type": "timedelta", "seconds": obj.total_seconds()})


def kwargs_to_elements(o):
    Logger.trace(f"kwargs before structure: {o}")
    if o["_type"] == "ButtonElement" and "rows" in o:
        rows = [
            elements.ButtonRows.assign([elements.ButtonElement.assign(show, value) for show, value in row.items()])
            for row in o["rows"]
            if isinstance(row, dict)
        ]
        return elements.ButtonFrameElement.assign(rows)
    if o["_type"] == "I18NContextElement":
        for k in o["kwargs"]:
            if (
                isinstance(o["kwargs"][k], dict)
                and hasattr(elements, o["kwargs"][k]["_type"])
                and (g := getattr(elements, o["kwargs"][k]["_type"]))
            ):
                o["kwargs"][k] = converter.structure(o["kwargs"][k]["element"], g)
            if (
                isinstance(o["kwargs"][k], dict)
                and (o["kwargs"][k].get("_type") == "MessageChain")
                and (msg_chain := exports.get("MessageChain"))
            ):
                o["kwargs"][k] = converter.structure(o["kwargs"][k]["element"], msg_chain)

    s = converter.structure(o, getattr(elements, o["_type"]))
    Logger.trace(f"kwargs after structure: {s}")
    return s


converter.register_structure_hook(MessageElement, lambda o, _: kwargs_to_elements(o))

# 从字典恢复为 TargetUnionInfo 对象（由于需要从数据库异步获取信息，这里实际只返回一个类本身用于占位，信息会在某个流程重新被刷新）
converter.register_structure_hook(TargetUnionInfo, lambda o, _: TargetUnionInfo)

# 从字典恢复为 SenderUnionInfo 对象（由于需要从数据库异步获取信息，这里实际只返回一个类本身用于占位，信息会在某个流程重新被刷新）
converter.register_structure_hook(SenderUnionInfo, lambda o, _: SenderUnionInfo)

converter.register_structure_hook(Locale, lambda o, _: Locale(o["locale"]))

converter.register_structure_hook(timedelta, lambda o, _: timedelta(seconds=o["seconds"]))

# EventName 的 Literal 分支只用于类型提示；反序列化时保留任意自定义事件名。
converter.register_structure_hook(EventName, lambda o, _: o)


__all__ = ["converter"]
