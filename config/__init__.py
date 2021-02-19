from configparser import ConfigParser


def config(path, q):
    cp = ConfigParser()
    cp.read(path)
    section = cp.sections()[0]
    value = cp.get(section, q)
    if value.upper() == 'TRUE':
        return True
    if value.upper() == 'FALSE':
        return False
    return value
