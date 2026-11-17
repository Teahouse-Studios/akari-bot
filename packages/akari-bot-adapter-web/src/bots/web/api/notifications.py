import asyncio
import hashlib
from datetime import UTC, datetime

import orjson

from core.config.base import BaseConfig
from core.constants.path import data_path
from core.i18n import Locale
from core.logger import Logger
from core.smtp import email_report_enabled, send_email

locale = Locale(BaseConfig.default_locale)

DEVICES_PATH = data_path / "private" / "web" / ".devices"
MAX_KNOWN_DEVICES = 100
SMTP_TIMEOUT = 15

_SECURITY_EVENT_KEYS = {
    "password_set": "web.security.email.event.password_set",
    "password_changed": "web.security.email.event.password_changed",
    "password_removed": "web.security.email.event.password_removed",
    "password_reset": "web.security.email.event.password_reset",
    "totp_enabled": "web.security.email.event.totp_enabled",
    "totp_disabled": "web.security.email.event.totp_disabled",
    "backup_codes_reset": "web.security.email.event.backup_codes_reset",
    "new_device_login": "web.security.email.event.new_device_login",
}

_UNSAFE_TEXT_CHARS = frozenset('<>"&')

_device_lock = asyncio.Lock()


def _sanitize_text(value: str, limit: int = 512) -> str:
    # 这些值会写入邮件 HTML，需剔除可用于注入标记的字符。
    cleaned = "".join(char for char in value if char.isprintable() and char not in _UNSAFE_TEXT_CHARS).strip()
    return cleaned[:limit] or "unknown"


def _read_devices() -> dict:
    if not DEVICES_PATH.exists():
        return {}
    try:
        with open(DEVICES_PATH, "rb") as file:
            data = orjson.loads(file.read())
    except Exception:
        Logger.warning("[WebUI] Failed to read known devices.")
        return {}
    devices = data.get("devices") if isinstance(data, dict) else None
    return devices if isinstance(devices, dict) else {}


def _write_devices(devices: dict) -> None:
    DEVICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEVICES_PATH, "wb") as file:
        file.write(orjson.dumps({"devices": devices}))


def _trim_devices(devices: dict) -> dict:
    # 未设置密码的 WebUI 可被扫描器触发记录，限制条目数避免文件无限增长。
    if len(devices) <= MAX_KNOWN_DEVICES:
        return devices
    ordered = sorted(
        devices.items(),
        key=lambda item: item[1].get("last_seen", 0) if isinstance(item[1], dict) else 0,
        reverse=True,
    )
    return dict(ordered[:MAX_KNOWN_DEVICES])


async def register_device(user_agent: str, ip: str) -> bool:
    user_agent = _sanitize_text(user_agent)
    # 以 UA 作为设备指纹；不纳入 IP，避免移动网络或代理切换导致误报。
    fingerprint = hashlib.sha256(user_agent.encode()).hexdigest()
    now = datetime.now(UTC).timestamp()

    async with _device_lock:
        try:
            devices = _read_devices()
            known = devices.get(fingerprint)
            is_new = not isinstance(known, dict)
            devices[fingerprint] = {
                "user_agent": user_agent,
                "first_seen": now if is_new else known.get("first_seen", now),
                "last_seen": now,
                "last_ip": ip,
            }
            _write_devices(_trim_devices(devices))
        except Exception:
            Logger.exception("[WebUI] Failed to update known devices: ")
            return False

    return is_new


async def notify_security_event(event: str, *, ip: str, user_agent: str) -> None:
    try:
        if not email_report_enabled():
            return

        event_key = _SECURITY_EVENT_KEYS.get(event)
        if event_key is None:
            Logger.warning(f'[WebUI] Unknown security event: "{event}".')
            return

        user_agent = _sanitize_text(user_agent)
        ip = _sanitize_text(ip, 64)
        event_name = locale.t(event_key)
        subject = f"[AkariBot] {locale.t('web.security.email.subject', event=event_name)}"

        if event == "new_device_login":
            body_key = "web.security.email.body.new_device_login"
        elif event == "password_reset":
            body_key = "web.security.email.body.password_reset"
        else:
            body_key = "web.security.email.body"

        body = locale.t(body_key, event=event_name, ip=ip, user_agent=user_agent)

        await asyncio.to_thread(send_email, subject, body, timeout=SMTP_TIMEOUT)
    except Exception:
        Logger.exception("[WebUI] Failed to send security notification email: ")
