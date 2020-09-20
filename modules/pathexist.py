import os
import re
from os.path import abspath


def pathexist(ss):
    ss = re.sub('_', '', ss)
    d = abspath('./assets/Favicon/' + ss + '/')
    if not os.path.exists(d):
        os.mkdir(d)
    else:
        pass
    ddd = abspath('./assets/Favicon/' + ss + '/Wiki.png')
    if not os.path.exists(ddd):
        return False
    else:
        return True


def pathexist2(ss):
    ddd = abspath('./home/wdljt/oasisakari/bot/assets/usercard/' + ss + '.png')
    if not os.path.exists(ddd):
        return False
    else:
        return True
