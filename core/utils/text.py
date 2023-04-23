def remove_suffix(string, suffix):
    return string[:-len(suffix)] if string.endswith(suffix) else string


def remove_prefix(string, prefix):
    return string[len(prefix):] if string.startswith(prefix) else string

