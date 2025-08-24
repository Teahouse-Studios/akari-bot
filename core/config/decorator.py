import inspect
from typing import Literal, TypeVar, Any, get_args
from types import UnionType


from core.exports import add_export
from . import CFGManager, ALLOWED_TYPES

T = TypeVar("T")


def _process_class(cls: type[T], table_name) -> type[T]:
    cls_annotations = {k: v for k, v in inspect.get_annotations(cls).items() if not k.startswith("__")}
    if not cls_annotations:
        cls_annotations = {k: Any for k, _ in vars(cls).items() if not k.startswith("__")}

    def __init__(self, **kwargs):
        for field_name, _ in cls_annotations.items():
            default_value = cls_annotations.get(field_name, None)
            __value = kwargs.get(field_name, default_value)
            setattr(self, field_name, __value)

    def __repr__(self):
        fields_str = ", ".join(f"{name}={getattr(self, name)!r}"
                               for name in cls_annotations)
        return f"{cls.__name__}({fields_str})"

    def __generate_config_file():
        """Generate a config file for the class."""
        for attr_name, attr_type in cls_annotations.items():
            if not attr_name.startswith("__"):
                __attr = getattr(cls, attr_name)
                __attr_type = attr_type
                if __attr_type not in ALLOWED_TYPES and (isinstance(__attr_type, UnionType) and any(
                        [k not in ALLOWED_TYPES for k in get_args(__attr_type)])):
                    __attr_type = None
                if attr_name not in CFGManager.values.keys():
                    CFGManager.load()
                    CFGManager.get(
                        attr_name,
                        __attr if __attr != "" else None,
                        get_args(__attr_type) if isinstance(__attr_type, UnionType) else attr_type,
                        False,
                        table_name,
                        _generate=True
                    )
                    CFGManager.save()

    __generate_config_file()
    cls.__repr__ = __repr__
    cls.__init__ = __init__

    return cls


def on_config(
    table_name: str,
    table_type: Literal["module", "bot", ""] = "",
    secret: bool = False
):

    def wrap(cls: type[T]):
        __type = table_type + "_" if table_type != "" else table_type
        return _process_class(cls, __type + table_name + "_secret" if secret else __type + table_name)
    return wrap


add_export(_process_class)
