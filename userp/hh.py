import re
def hh(w):
    value = w

    length = len(value)

    utf8_length = len(value.encode('utf-8'))

    length = (utf8_length - length) / 2 + length

    if int(length)>15:
        w = re.findall('..?.?.?.?.?.?.?.?.?.?.?.?.?.?', w)
        w = str(w)
        w = re.sub('\[','',w)
        w = re.sub('\]','',w)
        w = re.sub(',','-\n',w)
        w = re.sub('\'','',w)
        return(w)
    else:
        return(w)