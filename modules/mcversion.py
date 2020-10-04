from os.path import abspath


def mcversion():
    w = open(abspath('./assets/mcversion.txt'), 'r')
    s = w.read().split('\n')
    w.close()
    return (s)
