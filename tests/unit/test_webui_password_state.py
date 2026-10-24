"""bots.web: WebUI 密码文件状态监控测试。"""

import asyncio
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import bots.web.password_state as password_state
from core.database.models import StoredData
from core.tester import Tester, func_case


async def _clear_state():
    await StoredData.filter(stored_key=password_state.PASSWORD_STATE_KEY).delete()


async def _test_initialize_state():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        await _clear_state()
        with patch.object(password_state, "PASSWORD_PATH", password_path):
            await password_state.initialize_password_state()
        return (await password_state.get_password_present_state()) is False


async def _test_detects_removal():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        password_path.write_bytes(b"{}")
        await _clear_state()
        await password_state.set_password_present_state(True)
        with patch.object(password_state, "PASSWORD_PATH", password_path):
            password_path.unlink()
            first = await password_state.detect_password_removed()
            second = await password_state.detect_password_removed()
        return first is True and second is False and (await password_state.get_password_present_state()) is False


async def _test_added_file_is_not_notified():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        await _clear_state()
        await password_state.set_password_present_state(False)
        with patch.object(password_state, "PASSWORD_PATH", password_path):
            password_path.write_bytes(b"{}")
            detected = await password_state.detect_password_removed()
        return detected is False and (await password_state.get_password_present_state()) is True


async def _test_sync_prevents_removal():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        password_path.write_bytes(b"{}")
        await _clear_state()
        await password_state.sync_password_state(password_path)
        with patch.object(password_state, "PASSWORD_PATH", password_path):
            detected_before = await password_state.detect_password_removed()
            password_path.unlink()
            detected_after = await password_state.detect_password_removed()
        return detected_before is False and detected_after is True


async def _test_watcher_notifies_removal():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        await _clear_state()
        await password_state.set_password_present_state(True)

        notify = AsyncMock()
        task = None
        try:
            with (
                patch.object(password_state, "PASSWORD_PATH", password_path),
                patch.object(password_state, "PASSWORD_STATE_INTERVAL", 0.01),
                patch("bots.web.api.notifications.notify_security_event", notify),
            ):
                task = asyncio.create_task(password_state.watch_password_state())
                try:
                    for _ in range(50):
                        await asyncio.sleep(0.01)
                        if notify.called:
                            break
                finally:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

            return notify.called and notify.await_args.args[0] == "password_reset"
        finally:
            await _clear_state()


@func_case
async def test_webui_password_state(tester: Tester):
    """bots.web: WebUI 密码文件状态监控测试"""
    try:
        await tester.test(_test_initialize_state, "初始化密码状态测试")
        await tester.test(_test_detects_removal, "检测密码文件删除测试")
        await tester.test(_test_added_file_is_not_notified, "忽略密码文件新增测试")
        await tester.test(_test_sync_prevents_removal, "同步状态后不误报测试")
        await tester.test(_test_watcher_notifies_removal, "监控任务发送密码移除通知测试")
    finally:
        await _clear_state()
    return tester
