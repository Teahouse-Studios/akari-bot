import os
import re


def mcvrss():
    w = open('mcvrss.txt', 'r')
    s = w.read().split('\n')
    if '' in s:
        s.remove('')
    w.close()
    return (s)


def mcvrssa(group):
    q = mcvrss()
    if group in q:
        return ('该群已在订阅列表中。')
    else:
        wr = open('mcvrss.txt', 'a+')
        wr.write(re.sub(r'\n$', '', '\n' + group))
        wr.close()
        return ('已订阅。')


def mcvrssr(group):
    q = mcvrss()
    if group in q:
        q.remove(group)
        os.remove('mcvrss.txt')
        wr = open('mcvrss.txt', 'a')
        y = []
        h = ''
        for x in q:
            f = y.append(x + '\n')
        g = h.join(y)
        k = re.sub(r'\n$', '', g)
        wr.write(k)
        wr.close()
        return ('已移除订阅。')
    else:
        return ('此群不在订阅列表中。')
