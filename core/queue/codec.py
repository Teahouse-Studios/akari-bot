"""RPC values use declared types; dynamic hook values use an explicit allowlist.

No Python object, module name or callable supplied by a peer is imported. The
existing converter owns the wire representation of message and session objects.
"""

import math
import types
from typing import Any, Literal, Union, get_args, get_origin

from core.builtins.converter import converter


_value_types: dict[str, Any] = {}


def register_value_type(name: str, annotation: Any) -> None:
    if name in _value_types and _value_types[name] != annotation:
        raise ValueError(f"Duplicate RPC value type: {name}")
    _value_types[name] = annotation


def validate_type(annotation: Any) -> None:
    """Reject unsupported container contracts at registration, not in production."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is dict and args[0] is not str:
        raise TypeError("Typed RPC dictionaries require str keys for JSON transport")
    if origin is not None and origin not in (dict, list, Union, types.UnionType, Literal):
        raise TypeError(f"Unsupported RPC container annotation: {annotation!r}")
    if origin is not Literal:
        for argument in args:
            validate_type(argument)


def _dynamic_encode(value: Any) -> dict:
    if value is None or type(value) in (str, bool, int, float):
        if isinstance(value, float) and not math.isfinite(value):
            raise TypeError("RPC numbers must be finite")
        return {"kind": "scalar", "value": value}
    if isinstance(value, (list, tuple)):
        return {"kind": "list", "value": [_dynamic_encode(item) for item in value]}
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("RPC dictionary keys must be strings")
        return {"kind": "dict", "value": {key: _dynamic_encode(item) for key, item in value.items()}}
    for name, annotation in _value_types.items():
        if isinstance(value, annotation):
            return {"kind": "object", "type": name, "value": converter.unstructure(value, annotation)}
    raise TypeError(f"Unsupported dynamic RPC value: {type(value).__name__}")


def _dynamic_decode(value: dict) -> Any:
    match value:
        case {"kind": "scalar", "value": item} if item is None or type(item) in (str, bool, int, float):
            if isinstance(item, float) and not math.isfinite(item):
                raise TypeError("RPC numbers must be finite")
            return item
        case {"kind": "list", "value": list(items)}:
            return [_dynamic_decode(item) for item in items]
        case {"kind": "dict", "value": dict(items)}:
            return {key: _dynamic_decode(item) for key, item in items.items()}
        case {"kind": "object", "type": str(name), "value": item} if name in _value_types:
            return converter.structure(item, _value_types[name])
        case _:
            raise TypeError("Invalid dynamic RPC value")


def encode(value: Any, annotation: Any) -> Any:
    """Validate a value and encode it according to its declared wire type."""
    if annotation in (dict, list) and not isinstance(value, annotation):
        raise TypeError(f"Expected {annotation.__name__}")
    if annotation is Any or annotation in (dict, list):
        return _dynamic_encode(value)
    if annotation is None or annotation is type(None):
        if value is not None:
            raise TypeError("Expected None")
        return None
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        if value not in args:
            raise TypeError(f"Expected one of {args!r}")
        return value
    # Registered unions (notably message chains/nodes) already have a tagged
    # converter hook. Keep that representation instead of guessing a branch.
    if annotation in _value_types.values():
        if not isinstance(value, annotation):
            raise TypeError(f"Expected {annotation!r}")
        return converter.unstructure(value, annotation)
    if origin in (Union, types.UnionType):
        for index, branch in enumerate(args):
            try:
                return {"branch": index, "value": encode(value, branch)}
            except (TypeError, ValueError):
                pass
        raise TypeError(f"Value does not match {annotation!r}")
    if origin is list:
        if not isinstance(value, list):
            raise TypeError("Expected list")
        return [encode(item, args[0]) for item in value]
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("Expected dict")
        return {encode(key, args[0]): encode(item, args[1]) for key, item in value.items()}
    if annotation in (str, bool, int, float):
        if type(value) is not annotation and not (annotation is float and type(value) is int):
            raise TypeError(f"Expected {annotation.__name__}, got {type(value).__name__}")
        if annotation is float and not math.isfinite(value):
            raise TypeError("RPC numbers must be finite")
        return value
    if not isinstance(value, annotation):
        raise TypeError(f"Expected {annotation!r}")
    return converter.unstructure(value, annotation)


def decode(value: Any, annotation: Any) -> Any:
    if annotation is Any or annotation in (dict, list):
        result = _dynamic_decode(value)
        if annotation in (dict, list) and not isinstance(result, annotation):
            raise TypeError(f"Expected {annotation.__name__}")
        return result
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation in _value_types.values():
        return converter.structure(value, annotation)
    if origin in (Union, types.UnionType):
        if (
            not isinstance(value, dict)
            or type(value.get("branch")) is not int
            or not 0 <= value["branch"] < len(args)
            or "value" not in value
        ):
            raise TypeError(f"Invalid union value for {annotation!r}")
        return decode(value["value"], args[value["branch"]])
    if origin is list:
        if not isinstance(value, list):
            raise TypeError("Expected list")
        return [decode(item, args[0]) for item in value]
    if origin is dict:
        if not isinstance(value, dict):
            raise TypeError("Expected dict")
        return {decode(key, args[0]): decode(item, args[1]) for key, item in value.items()}
    if annotation in (None, type(None), str, bool, int, float) or origin is Literal:
        return encode(value, annotation)
    return converter.structure(value, annotation)
