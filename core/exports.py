# Export some functions to be dynamically called by the core module to avoid circular imports...
# Only use them when resolving circular import hell...

from typing import TypeVar, Type

T = TypeVar("T")


class Exports(dict):
    def register(self, exporter: Type[T], name: str | None = None):
        self[exporter.__name__ if not name else name] = exporter

    # 刻意收窄 dict.get 的签名以便调用方标注取回的类型。返回值声明为 T 而非 T | None：
    # 该 TypeVar 无从 name 推导，若声明为可选会使所有 isinstance(x, exports.get(...))
    # 形式的类型收窄失效，代价远大于此处标注的不严谨。
    def get(self, name: str, default: T | None = None) -> T:
        return self[name] if name in self else default


exports = Exports()


add_export = exports.register
