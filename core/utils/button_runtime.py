"""跨平台按钮 token 的注册与消费。"""

import re
import secrets
import time
from enum import Enum, auto
from typing import Any

from attrs import define
import orjson

from core.builtins.utils import confirm_command_default

BUTTON_TOKEN_PREFIX = "akb:"
BUTTON_EXPIRES = 3600
_CALLBACK_PATTERN = re.compile(r"<q:(.*?)>(.*)", re.DOTALL)


@define
class ButtonState:
    """按钮 token 对应的运行时状态。"""

    payload: str
    reply_id: str | None
    allowed_sender_id: str
    created_at: float
    used: bool = False


@define(frozen=True)
class RegisteredButton:
    """供平台渲染的按钮。"""

    label: str
    token: str


class ButtonConsumeStatus(Enum):
    """按钮消费结果。"""

    SUCCESS = auto()
    INVALID = auto()
    EXPIRED = auto()
    FORBIDDEN = auto()
    USED = auto()


@define(frozen=True)
class ButtonConsumeResult:
    """按钮消费后的数据。"""

    status: ButtonConsumeStatus
    payload: str | None = None
    reply_id: str | None = None


_button_registry: dict[str, ButtonState] = {}


def _generate_token() -> str:
    while True:
        token = BUTTON_TOKEN_PREFIX + secrets.token_urlsafe(9)
        if token not in _button_registry:
            return token


def _split_payload(data: str) -> tuple[str | None, str]:
    if match := _CALLBACK_PATTERN.fullmatch(data):
        return match.group(1), match.group(2)
    return None, data


def _decode_button_data(data: str | None) -> list[dict[str, str]]:
    if not data:
        return []
    try:
        decoded = orjson.loads(data)
    except orjson.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [row for row in decoded if isinstance(row, dict)]


def get_session_button_data(session_info: Any) -> list[dict[str, str]]:
    """根据会话临时状态取得最终按钮数据。"""
    tmp = session_info.tmp
    if tmp.get("wait_type") == "wait_confirm" and tmp.get("wait_active") == "yes":
        return [
            {
                session_info.locale.t("message.yes"): "confirm_yes",
                session_info.locale.t("message.no"): "confirm_no",
            }
        ]
    if tmp.get("wait_type") == "wait_next_message" and tmp.get("wait_active") == "yes":
        return _decode_button_data(tmp.get("wait_possibly_choices"))
    return _decode_button_data(tmp.get("button_data"))


def register_button_rows(button_data: list[dict[str, str]], allowed_sender_id: str) -> list[list[RegisteredButton]]:
    """注册按钮行并返回平台可用的短 token。"""
    now = time.time()
    expired_tokens = [token for token, state in _button_registry.items() if now - state.created_at > BUTTON_EXPIRES]
    for token in expired_tokens:
        del _button_registry[token]

    registered_rows = []
    for row in button_data:
        registered_row = []
        for label, data in row.items():
            reply_id, payload = _split_payload(data)
            token = _generate_token()
            _button_registry[token] = ButtonState(
                payload=payload,
                reply_id=reply_id,
                allowed_sender_id=allowed_sender_id,
                created_at=now,
            )
            registered_row.append(RegisteredButton(label=label, token=token))
        if registered_row:
            registered_rows.append(registered_row)
    return registered_rows


def consume_button(token: str, sender_id: str, now: float | None = None) -> ButtonConsumeResult:
    """校验并消费一个按钮 token。"""
    state = _button_registry.get(token)
    if state is None or not token.startswith(BUTTON_TOKEN_PREFIX):
        return ButtonConsumeResult(ButtonConsumeStatus.INVALID)

    current_time = time.time() if now is None else now
    if current_time - state.created_at > BUTTON_EXPIRES:
        del _button_registry[token]
        return ButtonConsumeResult(ButtonConsumeStatus.EXPIRED)
    if state.allowed_sender_id != sender_id:
        return ButtonConsumeResult(ButtonConsumeStatus.FORBIDDEN)
    if state.used:
        return ButtonConsumeResult(ButtonConsumeStatus.USED)

    state.used = True
    return ButtonConsumeResult(ButtonConsumeStatus.SUCCESS, state.payload, state.reply_id)


def normalize_button_payload(payload: str) -> str:
    """将平台确认按钮转换为现有确认文本。"""
    if payload == "confirm_yes":
        return confirm_command_default[0]
    if payload == "confirm_no":
        return "no"
    return payload


def _clear_button_registry() -> None:
    """清空按钮注册表，仅供测试隔离。"""
    _button_registry.clear()
