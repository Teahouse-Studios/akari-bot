from typing import Type, TypeVar, Dict, Any, get_type_hints

from . import Config

T = TypeVar('T')


class Item:
    def __init__(
        self,
        value: Any,
        default: Any = None,
        is_secret: bool = False,
        is_url: bool = False
    ):
        self.value = value
        self.default = default
        self.is_secret = is_secret
        self.is_url = is_url

    def __repr__(self):
        return f"Item(value={self.value}, default={self.default}, is_secret={self.is_secret}, is_url={self.is_url})"

def item(
    value: Any,
    default: Any = None,
    is_secret: bool = False,
    is_url: bool = False
) -> Item:
    """
    A decorator to define a configuration item.
    :param value: The value of the item.
    :param default: The default value of the item.
    :param is_secret: Whether the item is a secret.
    :param is_url: Whether the item is a URL.
    :return: An instance of Item.
    """
    return Item(value, default, is_secret, is_url)


def config():
    module_name = "TEMP_VAR_SHOULD_BE_REPLACED"

    def decorator(cls: Type[T]) -> Type[T]:
        if not hasattr(cls, '__annotations__'):
            raise TypeError("Config class must have type annotations")

        annotations = get_type_hints(cls)

        class_fields: Dict[str, Any] = {}
        for key, value in cls.__dict__.items():
            if not key.startswith('__'):
                class_fields[key] = value

        def __init__(self, **kwargs):
            for field_name, field_type in annotations.items():
                default_value = class_fields.get(field_name, None)
                __value = kwargs.get(field_name, default_value)

                if __value is not None and not isinstance(__value, field_type):
                    try:
                        __value = field_type(__value)
                    except (ValueError, TypeError) as e:
                        raise TypeError(f"Cannot convert value for {field_name} to {field_type}: {e}")

                setattr(self, field_name, __value)


        def __repr__(self):
            fields_str = ', '.join(f"{name}={getattr(self, name)!r}"
                                   for name in annotations)
            return f"{cls.__name__}({fields_str})"

        def __define_config_attrs():
            for attr_name, _ in cls.__dict__.items():
                if not attr_name.startswith('__'):
                    def get_config(cls):
                        __attr = getattr(cls, attr_name)
                        return Config(
                            attr_name,
                            __attr if not isinstance(__attr, Item) else __attr.default,
                            annotations.get(__attr),
                            True if isinstance(__attr, Item) and __attr.is_secret else False,
                            module_name,
                            True if isinstance(__attr, Item) and __attr.is_url else False,
                        )

                    setattr(cls, attr_name, property(get_config))

        __define_config_attrs()
        cls.__repr__ = __repr__
        cls.__init__ = __init__

        return cls

    return decorator
