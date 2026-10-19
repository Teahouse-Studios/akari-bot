"""bots.web.api 单元测试 - 敏感操作邮件通知。"""

import importlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pyotp
from fastapi.responses import Response

import bots.web.api.notifications as web_notify
from core.tester import Tester, func_case

# 包级 __init__ 的星号导入会用同名函数覆盖 auth 子模块属性，需从模块表取回。
web_auth = importlib.import_module("bots.web.api.auth")


class _Request:
    def __init__(self, body: dict, user_agent: str = "Mozilla/5.0 Test"):
        self._body = body
        self.client = SimpleNamespace(host="203.0.113.5")
        self.headers = {"user-agent": user_agent}

    async def json(self):
        return self._body


def _auth_patches(password_path: Path, notify: AsyncMock):
    return (
        patch.object(web_auth, "PASSWORD_PATH", password_path),
        patch.object(web_auth, "verify_jwt", lambda request: None),
        patch.object(web_auth, "_notify_security_event", notify),
        patch.object(web_auth, "sync_password_state", new=AsyncMock()),
    )


async def _test_smtp_notification_content():
    send_email = MagicMock()
    with (
        patch.object(web_notify, "email_report_enabled", return_value=True),
        patch.object(web_notify, "send_email", send_email),
    ):
        await web_notify.notify_security_event("password_changed", ip="203.0.113.5", user_agent="Mozilla/5.0 Test")

    subject, body = send_email.call_args.args
    return (
        subject.startswith("[AkariBot] ")
        and "密码已修改" in subject
        and "203.0.113.5" in body
        and "WebUI 密码已修改" in body
        and "Mozilla/5.0 Test" in body
    )


async def _test_new_device_notification_content():
    send_email = MagicMock()
    with (
        patch.object(web_notify, "email_report_enabled", return_value=True),
        patch.object(web_notify, "send_email", send_email),
    ):
        await web_notify.notify_security_event("new_device_login", ip="203.0.113.5", user_agent="Mozilla/5.0 Test")

    return "首次登录" in send_email.call_args.args[1]


async def _test_password_removed_notification_content():
    send_email = MagicMock()
    with (
        patch.object(web_notify, "email_report_enabled", return_value=True),
        patch.object(web_notify, "send_email", send_email),
    ):
        await web_notify.notify_security_event("password_removed", ip="unknown", user_agent="unknown")

    subject, body = send_email.call_args.args
    return "密码已移除" in subject and "密码已移除" in body and "{I18N:" not in subject + body


async def _test_skips_email_without_smtp():
    send_email = MagicMock()
    with (
        patch.object(web_notify, "email_report_enabled", return_value=False),
        patch.object(web_notify, "send_email", send_email),
    ):
        await web_notify.notify_security_event("password_changed", ip="203.0.113.5", user_agent="")

    return not send_email.called


async def _test_email_failure_is_swallowed():
    with (
        patch.object(web_notify, "email_report_enabled", return_value=True),
        patch.object(web_notify, "send_email", side_effect=RuntimeError("boom")),
        patch.object(web_notify.Logger, "exception"),
    ):
        await web_notify.notify_security_event("password_changed", ip="203.0.113.5", user_agent="")

    return True


async def _test_password_state_sync_failure_is_swallowed():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        with (
            patch.object(web_auth, "PASSWORD_PATH", password_path),
            patch.object(web_auth, "sync_password_state", new=AsyncMock(side_effect=RuntimeError("db down"))),
            patch.object(web_auth.Logger, "exception"),
        ):
            await web_auth._write_password_data({"password": "hash"})
            return password_path.exists()


async def _test_sanitizes_user_agent():
    send_email = MagicMock()
    with (
        patch.object(web_notify, "email_report_enabled", return_value=True),
        patch.object(web_notify, "send_email", send_email),
    ):
        await web_notify.notify_security_event("password_changed", ip="203.0.113.5", user_agent="<script>\nAgent")

    body = send_email.call_args.args[1]
    return "<script>" not in body and "scriptAgent" in body


async def _test_register_device_detects_new_device():
    with TemporaryDirectory() as temp_dir:
        devices_path = Path(temp_dir) / ".devices"
        with patch.object(web_notify, "DEVICES_PATH", devices_path):
            first = await web_notify.register_device("Mozilla/5.0 Test", "203.0.113.5")
            second = await web_notify.register_device("Mozilla/5.0 Test", "203.0.113.6")
            other = await web_notify.register_device("Mozilla/5.0 Other", "203.0.113.7")

        return first is True and second is False and other is True and devices_path.exists()


async def _test_device_write_failure_is_swallowed():
    with TemporaryDirectory() as temp_dir:
        with (
            patch.object(web_notify, "DEVICES_PATH", Path(temp_dir) / "missing" / ".devices"),
            patch.object(web_notify, "_write_devices", side_effect=OSError("read-only")),
            patch.object(web_notify.Logger, "exception"),
        ):
            return await web_notify.register_device("Mozilla/5.0 Test", "203.0.113.5") is False


async def _test_devices_are_trimmed():
    with TemporaryDirectory() as temp_dir:
        devices_path = Path(temp_dir) / ".devices"
        with (
            patch.object(web_notify, "DEVICES_PATH", devices_path),
            patch.object(web_notify, "MAX_KNOWN_DEVICES", 2),
        ):
            await web_notify.register_device("Mozilla/5.0 A", "203.0.113.1")
            await web_notify.register_device("Mozilla/5.0 B", "203.0.113.2")
            await web_notify.register_device("Mozilla/5.0 C", "203.0.113.3")

        return len(orjson.loads(devices_path.read_bytes())["devices"]) == 2


async def _test_login_notifies_new_device():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        password_path.write_bytes(orjson.dumps({"password": web_auth.ph.hash("password"), "last_updated": 0}))
        register_device = AsyncMock(return_value=True)
        notify = AsyncMock()
        with (
            patch.object(web_auth, "PASSWORD_PATH", password_path),
            patch.object(web_auth.MaliciousLoginRecords, "check_blocked", new=AsyncMock(return_value=False)),
            patch.object(web_auth, "register_device", register_device),
            patch.object(web_auth, "notify_security_event", notify),
        ):
            request = _Request({"password": "password"})
            result = await inspect.unwrap(web_auth.auth)(request)

        return (
            "data" in result
            and register_device.await_args.args == ("Mozilla/5.0 Test", "203.0.113.5")
            and notify.await_args.kwargs == {"ip": "203.0.113.5", "user_agent": "Mozilla/5.0 Test"}
        )


async def _test_login_without_password_notifies_new_device():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        register_device = AsyncMock(return_value=True)
        notify = AsyncMock()
        with (
            patch.object(web_auth, "PASSWORD_PATH", password_path),
            patch.object(web_auth.MaliciousLoginRecords, "check_blocked", new=AsyncMock(return_value=False)),
            patch.object(web_auth, "register_device", register_device),
            patch.object(web_auth, "notify_security_event", notify),
        ):
            request = _Request({})
            result = await inspect.unwrap(web_auth.auth)(request)

        return "data" in result and notify.await_args.args[0] == "new_device_login"


async def _test_password_endpoints_notify():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        notify = AsyncMock()
        path_patch, jwt_patch, notify_patch, state_patch = _auth_patches(password_path, notify)
        with path_patch, jwt_patch, notify_patch, state_patch:
            request = _Request({"new_password": "new-password"})
            response = await inspect.unwrap(web_auth.change_password)(request, Response())
            if response.status_code != 205 or notify.await_args.args[0] != "password_set":
                return False

            notify.reset_mock()
            password_path.write_bytes(orjson.dumps({"password": web_auth.ph.hash("old-password"), "last_updated": 0}))
            request = _Request({"password": "old-password", "new_password": "changed-password"})
            response = await inspect.unwrap(web_auth.change_password)(request, Response())
            if response.status_code != 205 or notify.await_args.args[0] != "password_changed":
                return False

            notify.reset_mock()
            request = _Request({"password": "changed-password"})
            await inspect.unwrap(web_auth.clear_password)(request)
            return notify.await_args.args[0] == "password_removed" and not password_path.exists()


async def _test_totp_endpoints_notify():
    with TemporaryDirectory() as temp_dir:
        password_path = Path(temp_dir) / ".password"
        password_path.write_bytes(orjson.dumps({"password": web_auth.ph.hash("password"), "last_updated": 0}))
        secret = pyotp.random_base32()
        notify = AsyncMock()
        path_patch, jwt_patch, notify_patch, state_patch = _auth_patches(password_path, notify)
        with path_patch, jwt_patch, notify_patch, state_patch:
            request = _Request({"secret": secret, "code": pyotp.TOTP(secret).now()})
            result = await inspect.unwrap(web_auth.enable_totp)(request)
            if result.get("message") != "success" or notify.await_args.args[0] != "totp_enabled":
                return False

            notify.reset_mock()
            request = _Request({"password": "password", "totp_code": pyotp.TOTP(secret).now()})
            result = await inspect.unwrap(web_auth.reset_backup_codes)(request)
            if result.get("message") != "success" or notify.await_args.args[0] != "backup_codes_reset":
                return False

            notify.reset_mock()
            request = _Request({"password": "password", "totp_code": pyotp.TOTP(secret).now()})
            result = await inspect.unwrap(web_auth.disable_totp)(request)
            return result.get("message") == "2FA disabled successfully" and notify.await_args.args[0] == "totp_disabled"


@func_case
async def test_webui_notify(tester: Tester):
    """bots.web.api: 敏感操作邮件通知测试"""
    await tester.test(_test_smtp_notification_content, "通知邮件内容测试")
    await tester.test(_test_new_device_notification_content, "新设备通知邮件内容测试")
    await tester.test(_test_password_removed_notification_content, "密码移除通知邮件内容测试")
    await tester.test(_test_skips_email_without_smtp, "SMTP 不可用时跳过测试")
    await tester.test(_test_email_failure_is_swallowed, "邮件发送失败不影响调用方测试")
    await tester.test(_test_password_state_sync_failure_is_swallowed, "密码状态同步失败不影响写入测试")
    await tester.test(_test_sanitizes_user_agent, "设备信息清理测试")
    await tester.test(_test_register_device_detects_new_device, "新设备识别测试")
    await tester.test(_test_devices_are_trimmed, "设备记录数量限制测试")
    await tester.test(_test_device_write_failure_is_swallowed, "设备记录写入失败测试")
    await tester.test(_test_login_notifies_new_device, "新设备登录通知测试")
    await tester.test(_test_login_without_password_notifies_new_device, "未设置密码时新设备登录通知测试")
    await tester.test(_test_password_endpoints_notify, "密码操作通知测试")
    await tester.test(_test_totp_endpoints_notify, "双重验证操作通知测试")

    return tester
