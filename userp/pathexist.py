import os
import re
from os.path import abspath
def pathexist(ss):
    ss = re.sub('_','',ss)
    d = abspath('./assests/Favicon/' + ss + '/')
    if not os.path.exists(d):
        os.mkdir(d)
    else:
        pass
    ddd = abspath('./assests/Favicon/' + ss + '/Wiki.png')
    if not os.path.exists(ddd):
        return False
    else:
        return True
