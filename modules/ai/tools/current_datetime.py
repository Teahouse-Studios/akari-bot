from datetime import datetime
import pytz


def current_datetime(timezone: str = "UTC") -> str:
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        return now.strftime("%Y-%m-%d %H:%M:%S %A") + f" ({timezone})"

    except Exception:
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S %A") + " (Server)"


__all__ = ["current_datetime"]
