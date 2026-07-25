# Export some functions to be dynamically called by the core module to avoid circular imports...
# Only use them when resolving circular import hell...

from typing import TypeVar, Type

T = TypeVar("T")


class Exports(dict):
    def register(self, exporter: Type[T], name=None):
        self[exporter.__name__ if not name else name] = exporter

    def get(self, name, default: T = None) -> T:
        return self[name] if name in self else default


exports = Exports()


add_export = exports.register
