"""SessionInfo 会话草稿：允许入口 hook 修改有限字段，成功才提交。"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo

WRITABLE_FIELDS = frozenset({"tmp", "prefixes", "messages", "bot_name", "muted", "locale_lang"})


class SessionDraftError(RuntimeError):
    """草稿使用错误（重复提交、已撤销、非法字段）。"""


def _copy_messages(messages):
    if messages is None:
        return None
    from core.builtins.message.chain import MessageChain, MessageNodes

    if isinstance(messages, MessageChain):
        return MessageChain.assign(list(messages.values))
    if isinstance(messages, MessageNodes):
        return MessageNodes.assign(
            [MessageChain.assign(list(node.values)) for node in messages.values], name=messages.name
        )
    raise SessionDraftError(f"messages must be MessageChain | MessageNodes | None, got {type(messages).__name__}")


class SessionDraft:
    """从已提交 SessionInfo 构建的独立草稿。"""

    __slots__ = (
        "_source",
        "_tmp",
        "_prefixes",
        "_messages",
        "_bot_name",
        "_muted",
        "_locale_lang",
        "_dirty",
        "_committed",
        "_revoked",
    )

    def __init__(self, session_info: "SessionInfo"):
        self._source = session_info
        self._tmp: dict[str, Any] = deepcopy(dict(getattr(session_info, "tmp", None) or {}))
        self._prefixes: list[str] = list(getattr(session_info, "prefixes", None) or [])
        self._messages = _copy_messages(getattr(session_info, "messages", None))
        self._bot_name = getattr(session_info, "bot_name", None)
        self._muted = getattr(session_info, "muted", None)
        locale = getattr(session_info, "locale", None)
        # Locale 实际字段是 locale（不是 lang）
        self._locale_lang = getattr(locale, "locale", None) or getattr(locale, "lang", None)
        self._dirty: set[str] = set()
        self._committed = False
        self._revoked = False

    @property
    def session_info(self):
        """只读视图；正式对象请勿经此写入。"""
        from .context import SessionInfoView

        return SessionInfoView(self._source)

    @property
    def source(self):
        return self.session_info

    @property
    def committed(self) -> bool:
        return self._committed

    @property
    def revoked(self) -> bool:
        return self._revoked

    def _ensure_open(self):
        if self._committed:
            raise SessionDraftError("Draft already committed.")
        if self._revoked:
            raise SessionDraftError("Draft revoked.")

    # ---- 可写容器：就地修改在 commit 时统一快照 ----

    @property
    def tmp(self) -> dict[str, Any]:
        self._ensure_open()
        self._dirty.add("tmp")
        return self._tmp

    @tmp.setter
    def tmp(self, value: dict[str, Any]):
        self._ensure_open()
        self._tmp = deepcopy(dict(value or {}))
        self._dirty.add("tmp")

    @property
    def prefixes(self) -> list[str]:
        self._ensure_open()
        self._dirty.add("prefixes")
        return self._prefixes

    @prefixes.setter
    def prefixes(self, value: list[str]):
        self._ensure_open()
        self._prefixes = list(value or [])
        self._dirty.add("prefixes")

    @property
    def messages(self):
        self._ensure_open()
        self._dirty.add("messages")
        return self._messages

    @messages.setter
    def messages(self, value):
        self._ensure_open()
        self._messages = _copy_messages(value)
        self._dirty.add("messages")

    @property
    def bot_name(self) -> str | None:
        self._ensure_open()
        return self._bot_name

    @bot_name.setter
    def bot_name(self, value: str | None):
        self._ensure_open()
        self._bot_name = value
        self._dirty.add("bot_name")

    @property
    def muted(self) -> bool | None:
        self._ensure_open()
        return self._muted

    @muted.setter
    def muted(self, value: bool | None):
        self._ensure_open()
        self._muted = value
        self._dirty.add("muted")

    @property
    def locale_lang(self) -> str | None:
        self._ensure_open()
        return self._locale_lang

    @locale_lang.setter
    def locale_lang(self, value: str):
        self._ensure_open()
        if not isinstance(value, str) or not value.strip():
            raise SessionDraftError("locale_lang must be a non-empty str")
        self._locale_lang = value
        self._dirty.add("locale_lang")

    def set_tmp(self, key: str, value: str) -> None:
        self._ensure_open()
        if not isinstance(key, str) or not isinstance(value, str):
            raise SessionDraftError("tmp keys/values must be str")
        self._tmp[key] = value
        self._dirty.add("tmp")

    def pop_tmp(self, key: str, default: Any = None) -> Any:
        self._ensure_open()
        self._dirty.add("tmp")
        return self._tmp.pop(key, default)

    def revoke(self) -> None:
        self._revoked = True

    @property
    def dirty_fields(self) -> frozenset[str]:
        return frozenset(self._dirty)

    def _prepare_commit(self) -> dict[str, Any]:
        tmp_snapshot: dict[str, str] = {}
        for k, v in self._tmp.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise SessionDraftError(f"tmp entries must be str->str, got {type(k).__name__}->{type(v).__name__}")
            tmp_snapshot[k] = v
        prefixes = list(self._prefixes)
        for p in prefixes:
            if not isinstance(p, str):
                raise SessionDraftError(f"prefixes entries must be str, got {type(p).__name__}")
        messages = _copy_messages(self._messages)
        bot_name = self._bot_name
        if bot_name is not None and not isinstance(bot_name, str):
            raise SessionDraftError("bot_name must be str | None")
        muted = self._muted
        if muted is not None and not isinstance(muted, bool):
            raise SessionDraftError("muted must be bool | None")
        locale_lang = self._locale_lang
        if "locale_lang" in self._dirty and (not isinstance(locale_lang, str) or not locale_lang.strip()):
            raise SessionDraftError("locale_lang must be a non-empty str")
        return {
            "tmp": tmp_snapshot,
            "prefixes": prefixes,
            "messages": messages,
            "bot_name": bot_name,
            "muted": muted,
            "locale_lang": locale_lang,
        }

    def commit(self) -> "SessionInfo":
        self._ensure_open()
        if not self._dirty:
            self._committed = True
            return self._source
        prepared = self._prepare_commit()
        target = self._source
        # Locale 对象也先构造，与字段校验同属"准备"阶段；构造失败则整次提交不发布，
        # 避免其余字段已写回而 locale 静默降级造成的半提交。
        new_locale = None
        if "locale_lang" in self._dirty:
            from core.i18n import Locale

            new_locale = Locale(prepared["locale_lang"])
        if "tmp" in self._dirty:
            if not hasattr(target, "tmp") or target.tmp is None:
                target.tmp = {}
            target.tmp.clear()
            target.tmp.update(prepared["tmp"])
        if "prefixes" in self._dirty:
            target.prefixes = prepared["prefixes"]
        if "messages" in self._dirty:
            target.messages = prepared["messages"]
        if "bot_name" in self._dirty:
            target.bot_name = prepared["bot_name"]
        if "muted" in self._dirty:
            target.muted = prepared["muted"]
        if new_locale is not None:
            target.locale = new_locale
        self._committed = True
        return target


def build_session_draft(session_info: "SessionInfo") -> SessionDraft:
    return SessionDraft(session_info)


__all__ = ["SessionDraft", "SessionDraftError", "WRITABLE_FIELDS", "build_session_draft"]
