import re


def ddk(str1):
    a = re.sub('<dd>', '', str1)
    a = re.sub('</dd>', '', a)
    return (a)
