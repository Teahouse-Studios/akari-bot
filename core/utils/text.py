import sys
from typing import TypeVar

T = TypeVar("T", str, bytes, bytearray)

if sys.version_info.minor > 8:  # PY39
    def remove_suffix(string: T, suffix: T) -> T:
        return string.removesuffix(suffix)

    def remove_prefix(string: T, prefix: T) -> T:
        return string.removeprefix(prefix)
else:
    def remove_suffix(string: T, suffix: T) -> T:
        return string[:-len(suffix)] if string.endswith(suffix) else string

    def remove_prefix(string: T, prefix: T) -> T:
        return string[len(prefix):] if string.startswith(prefix) else string
