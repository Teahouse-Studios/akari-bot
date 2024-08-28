from datetime import datetime


def strptime2ts(date_string):
    """Convert a date string to a timestamp."""
    return datetime.fromisoformat(date_string).timestamp()
