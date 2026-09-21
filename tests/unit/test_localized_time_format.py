"""本地化时间格式化的非 ASCII 字面文本测试。"""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import core.smtp as smtp
from core.builtins.message.elements import FormattedTimeElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import FetchedMessageSession
from core.i18n import Locale, safe_strftime
from core.logger import Logger
from core.tester import func_case, Tester

# 2009-02-13 23:31:30 UTC
FIXED_TIMESTAMP = 1234567890.0
KO_DATE_FORMAT = "%Y년 %m월 %d일"
KO_TIME_FORMAT = "%H:%M:%S"
KO_TIME_TEXT = "2009년 02월 14일 07:31:30"
KO_RENDERED = f"{KO_TIME_TEXT} (UTC+8)"


def _ko_locale() -> Locale:
    locale = Locale("ko_kr")
    if locale.t("time.date.format") != KO_DATE_FORMAT or locale.t("time.time.format") != KO_TIME_FORMAT:
        Logger.error("ko_kr locale data is missing, cannot verify localized time format")
        return None
    return locale


def _directive_pattern(fmt: str) -> str:
    return "".join(r"\d+" if token.startswith("%") else re.escape(token) for token in re.split(r"(%[A-Za-z%])", fmt))


def _session_info() -> SessionInfo:
    return SessionInfo(
        target_id="TEST|Group|localized_time",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        locale=_ko_locale(),
        tz_offset="+8",
        timezone_offset=timedelta(hours=8),
    )


def _test_safe_strftime_keeps_non_ascii_literals() -> bool:
    locale = _ko_locale()
    if locale is None:
        return False
    rendered = safe_strftime(datetime(2009, 2, 14, 7, 31, 30), f"{KO_DATE_FORMAT} {KO_TIME_FORMAT}")
    if rendered != KO_TIME_TEXT:
        Logger.error(f"Unexpected localized time: {rendered!r}")
        return False
    return True


def _test_session_format_time_localizes_non_ascii_format() -> bool:
    rendered = FetchedMessageSession(session_info=_session_info()).format_time(FIXED_TIMESTAMP)
    if rendered != KO_RENDERED:
        Logger.error(f"Unexpected format_time result: {rendered!r}")
        return False
    return True


def _test_formatted_time_element_localizes_non_ascii_format() -> bool:
    element = FormattedTimeElement.assign(FIXED_TIMESTAMP)
    rendered = element.to_str(_session_info())
    if rendered != KO_RENDERED:
        Logger.error(f"Unexpected formatted time element: {rendered!r}")
        return False
    return True


def _test_report_email_html_localizes_non_ascii_format() -> bool:
    with patch.object(smtp, "locale", _ko_locale()):
        html = smtp._build_email_html("body", "footer")
    if not re.search(_directive_pattern(f"{KO_DATE_FORMAT} {KO_TIME_FORMAT}"), html):
        Logger.error(f"Report email html lacks the localized timestamp: {html!r}")
        return False
    return True


@func_case
async def test_localized_time_format(tester: Tester):
    """本地化时间的非 ASCII 格式串测试"""
    await tester.test(_test_safe_strftime_keeps_non_ascii_literals, "safe_strftime 保留非 ASCII 字面文本")
    await tester.test(_test_session_format_time_localizes_non_ascii_format, "会话 format_time 本地化时间")
    await tester.test(_test_formatted_time_element_localizes_non_ascii_format, "FormattedTimeElement 本地化时间")
    await tester.test(_test_report_email_html_localizes_non_ascii_format, "上报邮件 HTML 本地化时间")

    return tester
