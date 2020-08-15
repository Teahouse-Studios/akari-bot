def mcversion():
    w = open('mcversion.txt', 'r')
    s = w.read().split('\n')
    w.close()
    return (s)

