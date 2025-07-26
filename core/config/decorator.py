import inspect
from typing import Type, TypeVar, Any

from core.exports import add_export

from . import Config, Item, CFGManager

T = TypeVar('T')


def _process_class(cls: Type[T], table_name) -> Type[T]:
    cls_annotations = {k: v for k, v in inspect.get_annotations(cls).items() if not k.startswith("__")}
    if not cls_annotations:
        cls_annotations = {k: Any for k, _ in vars(cls).items() if not k.startswith("__")}

    def __init__(self, **kwargs):
        for field_name, field_type in cls_annotations.items():
            default_value = cls_annotations.get(field_name, None)
            __value = kwargs.get(field_name, default_value)

            if __value is not None and not isinstance(__value, field_type):
                try:
                    __value = field_type(__value)
                except (ValueError, TypeError) as e:
                    raise TypeError(f"Cannot convert value for {field_name} to {field_type}: {e}")

            setattr(self, field_name, __value)

    def __repr__(self):
        fields_str = ', '.join(f"{name}={getattr(self, name)!r}"
                               for name in cls_annotations)
        return f"{cls.__name__}({fields_str})"

    def __define_config_attrs():
        for attr_name, attr_type in cls_annotations.items():
            if not attr_name.startswith('__'):
                __attr = getattr(cls, attr_name)
                delattr(cls, attr_name)
                setattr(cls, '__' + attr_name, __attr)

                def get_config(cls):
                    return Config(
                        attr_name,
                        __attr.default if isinstance(__attr, Item) else __attr,
                        attr_type,
                        True if isinstance(__attr, Item) and __attr.is_secret else False,
                        __attr.table_name if isinstance(__attr, Item) else table_name,
                        True if isinstance(__attr, Item) and __attr.is_url else False,
                    )

                setattr(cls, attr_name, property(get_config))

    def __generate_config_file():
        """Generate a config file for the class."""
        for attr_name, attr_type in cls_annotations.items():
            if not attr_name.startswith('__'):
                __attr = getattr(cls, attr_name)
                if attr_name not in CFGManager.values.keys():
                    CFGManager.write(
                        attr_name,
                        None,
                        attr_type,
                        True if isinstance(__attr, Item) and __attr.is_secret else False,
                        table_name,
                        _generate=True
                    )

    __generate_config_file()
    __define_config_attrs()
    cls.__repr__ = __repr__
    cls.__init__ = __init__

    return cls


def on_config(cls=None, table_name=None):
    def wrap(cls):
        return _process_class(cls, table_name)

    if cls is None:
        return wrap
    return wrap(cls)


add_export(_process_class)
