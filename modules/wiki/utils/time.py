from datetime import datetime


def strptime2ts(date_string):
    """Convert a date string to a timestamp."""
    return ((datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')).timestamp()
            + datetime.now().timestamp() - datetime.utcnow().timestamp())
