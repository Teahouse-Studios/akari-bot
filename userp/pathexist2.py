import os
import re

def pathexist(ss):
    ddd = 'D:/AkariBot/usercard/' + ss + '.png'
    if not os.path.exists(ddd):
        return False
    else:
        return True
