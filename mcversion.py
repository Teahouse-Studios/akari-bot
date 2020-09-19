from os.path import abspath


def mcversion():
    w = open(abspath('./mcversion.txt'), 'r')
    s = w.read().split('\n')
    w.close()
    return (s)
