from configparser import ConfigParser
import sys
from os.path import abspath

def config(q):
    cp = ConfigParser()
    cp.read(abspath("./config/config.cfg"))
    section = cp.sections()[0]
    return(cp.get(section,q))