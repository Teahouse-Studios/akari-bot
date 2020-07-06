import os
import re

def pathexist(ss):
    ddd = '/home/wdljt/oasisakari/bot/assests/usercard' + ss + '.png'
    if not os.path.exists(ddd):
        return False
    else:
        return True
