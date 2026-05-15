from datetime import datetime
import pytz


current_datetime_desc = {
    "type": "function",
    "function": {
        "name": "current_datetime",
        "description": "Get the current date, time, and day of the week.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Time zone, supports time zone identifier or UTC offset.",
                    "default": "UTC",
                }
            },
        },
    },
}


def current_datetime(timezone: str = "UTC") -> str:
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        return now.strftime("%Y-%m-%d %H:%M:%S %A") + f" ({timezone})"

    except Exception:
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S %A") + " (Server)"


__all__ = ["current_datetime", "current_datetime_desc"]
