import re


def hh(w):
    if len(w) > 15:
        w = [w[i:i+15] for i in range(0, len(w), 15)]
        w = '-\n'.join(w)
    return w


def hh1(w):
    w = '理由“' + w + '”'
    if len(w) > 25:
        w = [w[i:i+25] for i in range(0, len(w), 25)]
        w = '-\n'.join(w)
    return w
