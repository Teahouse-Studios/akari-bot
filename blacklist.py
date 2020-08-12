def blacklist():
    w = open('blacklist.txt', 'r')
    s = w.read().split('\n')
    return (s)
    w.close()
