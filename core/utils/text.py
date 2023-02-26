def remove_suffix(string, suffix):
    return string[:-len(suffix)] if string.endswith(suffix) else string
