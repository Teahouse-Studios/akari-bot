import sys
from configparser import ConfigParser
from os.path import abspath


def iwlist():
    cp = ConfigParser()
    cp.read(abspath("./modules/interwikilist/list.cfg"))
    section = cp.sections()[0]
    return (cp.options(section))


def iwlink(iw):
    cp = ConfigParser()
    cp.read(abspath("./modules/interwikilist/list.cfg"))
    section = cp.sections()[0]
    return (cp.get(section, iw))
