def mcversion():
    w = open('mcversion.txt','r')
    s = w.read().split('\n')
    return(s)
    w.close()