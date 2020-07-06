import os
import re

def pathexist(ss):
    ss = re.sub('_','',ss)
    d = '/home/wdljt/oasisakari/bot/assests/Favicon/' + ss + '/'
    if not os.path.exists(d):
        os.mkdir(d)
    else:
        pass
    ddd = '/home/wdljt/oasisakari/bot/assests/Favicon/' + ss + '/Wiki.png'
    if not os.path.exists(ddd):
        return False
    else:
        return True
