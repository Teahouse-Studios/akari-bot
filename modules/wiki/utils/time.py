import datetime


def strptime2ts(date_string):
    """Convert a date string to a timestamp."""
    return ((datetime.datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')).timestamp()
            + datetime.datetime.now().timestamp() - datetime.datetime.now(datetime.UTC).timestamp())
