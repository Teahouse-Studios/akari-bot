import re


def UTC8(str1, outtype):
    if str1 in ['infinity', 'infinite']:
        return '无限期'
    else:
        q = re.match(r'(.*)-(.*)-(.*)T(.*):(.*):(.*)Z', str1)
        if not q:
            q = re.match(r'(....)(..)(..)(..)(..)(..)', str1)
        y = int(q.group(1))
        m = int(q.group(2))
        d = int(q.group(3))
        h = int(q.group(4))
        mi = int(q.group(5))
        #        s = int(q.group(6))

        h = h + 8
        if h > 24:
            d = d + 1
            h = h - 24
        else:
            pass
        if m == 2:
            if y % 100 == 0:
                if y % 400 == 0:
                    pass
                else:
                    if d == 29:
                        m = m + 1
                        d = d - 28
                    else:
                        pass
            if d == 29:
                if y % 4 == 0:
                    pass
                else:
                    m = m + 1
                    d = d - 28
            if d == 30:
                m = m + 1
                d = d - 29
            else:
                pass
        else:
            pass
        if d == 31:
            if m == 4 or m == 6 or m == 9 or m == 11:
                m = m + 1
                d = d - 30
            else:
                pass
        else:
            pass
        if d == 32:
            m = m + 1
            d = d - 31
        if m == 13:
            m = m - 12
            y = y + 1
        if h == 24:
            if mi != 0:
                h = h - 24
        if outtype == 'onlytimenoutc':
            return (str(h) + '时' + str(mi) + '分')
        elif outtype == 'onlytime':
            return (str(h) + '时' + str(mi) + '分' + '（UTC+8）')
        elif outtype == 'full':
            return (str(y) + '年' + str(m) + '月' + str(d) + '日' + str(h) + '时' + str(mi) + '分' + '（UTC+8）')
        elif outtype == 'notimezone':
            return (str(y) + '年' + str(m) + '月' + str(d) + '日' + str(h) + '时' + str(mi) + '分')
