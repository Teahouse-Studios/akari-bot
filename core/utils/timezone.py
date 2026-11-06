"""机器人的时间工具。"""

from datetime import date, datetime, timedelta, timezone as dt_timezone, tzinfo

from core.config.base import CoreConfig
from core.logger import Logger
from core.utils.func import format_offset, parse_offset


def core_offset() -> timedelta:
    """取核心默认偏移量。"""
    raw = CoreConfig.timezone_offset
    offset = parse_offset(raw)
    if offset is None:
        Logger.warning(f"Invalid core timezone offset {raw!r}, fallback to UTC.")
        return timedelta()
    return offset


def core_tz() -> tzinfo:
    """取核心默认时区。"""
    return dt_timezone(core_offset())


def core_offset_text() -> str:
    """取规范化的核心默认偏移量字符串。"""
    return format_offset(core_offset())


def core_now(tz: tzinfo | None = None) -> datetime:
    """取核心时区（或指定时区）的当前时间。"""
    return datetime.now(tz or core_tz())


def core_today(tz: tzinfo | None = None) -> date:
    """取核心时区（或指定时区）的当前日期。"""
    return core_now(tz).date()


def core_midnight(tz: tzinfo | None = None) -> datetime:
    """取核心时区（或指定时区）的今日零点。"""
    return core_now(tz).replace(hour=0, minute=0, second=0, microsecond=0)


__all__ = [
    "core_midnight",
    "core_now",
    "core_offset",
    "core_offset_text",
    "core_today",
    "core_tz",
    "format_offset",
    "parse_offset",
]
