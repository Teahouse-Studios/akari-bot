from __future__ import annotations

from attrs import asdict
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.features import Features

# 就地注入后返回原对象，故须保留调用方传入的具体子类型（如 FetchedSessionInfo）
_SessionT = TypeVar("_SessionT", bound="SessionInfo")


def inject_features(session: _SessionT, features: Features) -> _SessionT:
    for feature in (d := asdict(features)):
        setattr(session, feature, d[feature])
    return session
