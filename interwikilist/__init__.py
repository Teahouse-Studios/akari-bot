from configparser import ConfigParser
import sys
from os.path import abspath
def iwlist():
    cp = ConfigParser()
    cp.read(abspath("..")+"/interwikilist/list.cfg")
    section = cp.sections()[0]
    return(cp.options(section))

def iwlink(iw):
    cp = ConfigParser()
    cp.read(abspath("..")+"/home/wdljt/oasisakari/bot/interwikilist/list.cfg")
    section = cp.sections()[0]
    return(cp.get(section,iw))