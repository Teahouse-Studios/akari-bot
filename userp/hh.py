import re


def hh(w):
    if int(w) > 15:
        w = re.findall('..?.?.?.?.?.?.?.?.?.?.?.?.?.?', w)
        w = str(w)
        w = re.sub('\[', '', w)
        w = re.sub('\]', '', w)
        w = re.sub(',', '-\n', w)
        w = re.sub('\'', '', w)
        return (w)
    else:
        return (w)

def hh1(w):
    w = '理由“' + w + '”'
    if len(w) > 25:
        w = re.findall('..?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?.?', w)
        w = str(w)
        w = re.sub('\[', '', w)
        w = re.sub('\]', '', w)
        w = re.sub(',', '-\n', w)
        w = re.sub('\'', '', w)
        return (w)
    else:
        return (w)