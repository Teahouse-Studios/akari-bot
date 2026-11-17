"""Parser / 出站入口 hook 的上下文对象。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar

from attrs import define, field as attrs_field

from .draft import SessionDraft
from .points import HookPoint
from .results import Continue, Handled, RecoveryProposal, RewriteTrigger, Stop, StopScope

if TYPE_CHECKING:
    from core.builtins.bot import Bot
    from core.builtins.session.info import SessionInfo


def _readonly_value(value: Any, memo: dict[int, Any] | None = None) -> Any:
    if callable(value):
        raise AttributeError("Methods are not available through a read-only session view")
    if type(value) in (str, bytes, int, float, complex, bool, type(None), date, datetime, time, timedelta, Decimal):
        return value
    if memo is None:
        memo = {}
    if id(value) in memo:
        return memo[id(value)]
    if isinstance(value, dict):
        result = {}
        memo[id(value)] = result
        result.update((_readonly_value(key, memo), _readonly_value(item, memo)) for key, item in value.items())
        return result
    if isinstance(value, list):
        result = []
        memo[id(value)] = result
        result.extend(_readonly_value(item, memo) for item in value)
        return result
    if isinstance(value, (tuple, set, frozenset)):
        result = type(value)(_readonly_value(item, memo) for item in value)
        memo[id(value)] = result
        return result

    from core.builtins.message.chain import MessageChain, MessageNodes
    from core.i18n import Locale

    if isinstance(value, (MessageChain, MessageNodes, Locale)):
        # 这些值对象允许在独立副本上使用翻译/消息 API；复制失败必须拒绝读取，不能退回源引用。
        return deepcopy(value)
    return _ReadOnlyObjectView(value)


class _ReadOnlyObjectView:
    __slots__ = ("_target",)

    def __init__(self, target: Any):
        object.__setattr__(self, "_target", target)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return _readonly_value(getattr(self._target, name))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"Object view is read-only ({name!r})")


class SessionInfoView:
    """SessionInfo 的只读视图：阻止就地写入身份与可变容器。"""

    __slots__ = ("_info", "_tmp", "_prefixes")

    def __init__(self, info: "SessionInfo"):
        object.__setattr__(self, "_info", info)
        object.__setattr__(self, "_tmp", MappingProxyType(_readonly_value(dict(getattr(info, "tmp", None) or {}))))
        object.__setattr__(self, "_prefixes", tuple(_readonly_value(list(getattr(info, "prefixes", None) or ()))))

    def __getattr__(self, name: str) -> Any:
        if name == "tmp":
            return self._tmp
        if name == "prefixes":
            return self._prefixes
        if name.startswith("_"):
            raise AttributeError(name)
        return _readonly_value(getattr(self._info, name))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"SessionInfoView is read-only; use ctx.draft to write ({name!r})")

    def __repr__(self) -> str:
        return f"SessionInfoView({self._info!r})"


@dataclass
class OutgoingPayload:
    """出站 before_send 的可变载荷。"""

    chain: Any
    quote: bool = True
    message_ids: list | None = None

    @staticmethod
    def _clone_chain(chain: Any) -> Any:
        from core.builtins.message.chain import MessageChain, MessageNodes

        if isinstance(chain, MessageChain):
            return MessageChain.assign(list(chain.values))
        if isinstance(chain, MessageNodes):
            return MessageNodes.assign(
                [MessageChain.assign(list(node.values)) for node in chain.values], name=chain.name
            )
        if isinstance(chain, (str, bytes, int, float, bool, type(None))):
            return chain
        if isinstance(chain, list):
            return [OutgoingPayload._clone_chain(item) for item in chain]
        # 其他带 copy 的元素级对象按自身语义复制；失败则拒绝快照，避免共享引用
        if hasattr(chain, "copy"):
            return chain.copy()
        return deepcopy(chain)

    def snapshot(self) -> "OutgoingPayload":
        ids = list(self.message_ids) if self.message_ids is not None else None
        return OutgoingPayload(chain=self._clone_chain(self.chain), quote=self.quote, message_ids=ids)

    def apply_from(self, other: "OutgoingPayload") -> None:
        # 提交时再断开一次引用：成功 hook 若继续持有草稿链，之后的就地修改不得污染正式结果
        self.chain = self._clone_chain(other.chain)
        self.quote = other.quote
        if other.message_ids is not None:
            self.message_ids = list(other.message_ids)


@define
class ParserHookContext:
    """入口订阅执行时的受控上下文。"""

    # 结果类型作为上下文能力暴露，内置模块无需为简单控制流重复导入。
    Continue: ClassVar[type[Continue]] = Continue
    Stop: ClassVar[type[Stop]] = Stop
    StopScope: ClassVar[type[StopScope]] = StopScope
    Handled: ClassVar[type[Handled]] = Handled
    RecoveryProposal: ClassVar[type[RecoveryProposal]] = RecoveryProposal
    RewriteTrigger: ClassVar[type[RewriteTrigger]] = RewriteTrigger

    point: HookPoint
    msg: "Bot.MessageSession"
    module_name: str | None = None
    data: dict[str, Any] = attrs_field(factory=dict)
    command_first_word: str | None = None
    draft: SessionDraft | None = None
    outgoing: OutgoingPayload | None = None
    _session_view: SessionInfoView | None = None

    @property
    def session_info(self) -> SessionInfoView:
        """只读视图；可写字段请用 ``draft``。"""
        if self._session_view is None:
            self._session_view = SessionInfoView(self.msg.session_info)
        return self._session_view

    @property
    def trigger_msg(self) -> str:
        return self.msg.trigger_msg

    @property
    def parsed_msg(self) -> dict | None:
        parsed = getattr(self.msg, "parsed_msg", None)
        if parsed is None:
            return None
        # 深拷贝：hook 对嵌套列表/字典的就地修改不得写回原解析结果
        return deepcopy(dict(parsed))


__all__ = ["ParserHookContext", "OutgoingPayload", "SessionInfoView"]
