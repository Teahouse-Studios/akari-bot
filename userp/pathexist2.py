import os
import re

def pathexist(ss):
    ddd = '/home/oasisakari/botassests/usercard' + ss + '.png'
    if not os.path.exists(ddd):
        return False
    else:
        return True
