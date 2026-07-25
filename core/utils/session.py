from __future__ import annotations

from attrs import asdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo
    from core.builtins.session.features import Features


def inject_features(session: SessionInfo, features: Features) -> SessionInfo:
    for feature in (d := asdict(features)):
        setattr(session, feature, d[feature])
    return session
