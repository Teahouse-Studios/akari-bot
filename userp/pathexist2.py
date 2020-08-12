import os
import re
from os.path import abspath


def pathexist(ss):
    ddd = abspath('./assests/usercard' + ss + '.png')
    if not os.path.exists(ddd):
        return False
    else:
        return True
