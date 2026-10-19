import asyncio
from datetime import UTC, datetime
from pathlib import Path

from core.constants.path import data_path
from core.database.models import StoredData
from core.logger import Logger

PASSWORD_PATH = data_path / "private" / "web" / ".password"

# 密码是否存在的变化记录在 StoredData 的单键中，避免为单个状态新建表。
PASSWORD_STATE_KEY = "web|password_present"
PASSWORD_STATE_INTERVAL = 30


async def get_password_present_state() -> bool | None:
    stored = await StoredData.get_or_none(stored_key=PASSWORD_STATE_KEY)
    if stored is None or not isinstance(stored.value, dict):
        return None
    return bool(stored.value.get("present"))


async def set_password_present_state(present: bool) -> None:
    await StoredData.update_or_create(
        defaults={"value": {"present": present, "updated_at": datetime.now(UTC).timestamp()}},
        stored_key=PASSWORD_STATE_KEY,
    )


async def sync_password_state(password_path: Path | None = None) -> None:
    password_path = password_path or PASSWORD_PATH
    await set_password_present_state(password_path.exists())


async def initialize_password_state() -> None:
    if (await get_password_present_state()) is None:
        await sync_password_state()


async def detect_password_removed() -> bool:
    present = PASSWORD_PATH.exists()
    state = await get_password_present_state()
    if state is None:
        await set_password_present_state(present)
        return False
    if state and not present:
        await set_password_present_state(False)
        return True
    if not state and present:
        await set_password_present_state(True)
    return False


async def watch_password_state() -> None:
    from bots.web.api.notifications import notify_security_event

    try:
        await initialize_password_state()
    except Exception:
        Logger.exception("[WebUI] Failed to initialize password state: ")

    while True:
        try:
            removed = await detect_password_removed()
        except Exception:
            Logger.exception("[WebUI] Failed to check password state: ")
            removed = False

        if removed:
            Logger.warning("[WebUI] Detected external password removal.")
            await notify_security_event("password_removed", ip="unknown", user_agent="unknown")

        await asyncio.sleep(PASSWORD_STATE_INTERVAL)
