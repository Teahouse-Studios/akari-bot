from configparser import ConfigParser
from os.path import abspath

path = abspath("./modules/interwikilist/")
print(path)

def iwlist():
    cp = ConfigParser()
    cp.read(path+"/list.cfg")
    print(path)
    section = cp.sections()[0]
    return (cp.options(section))


def iwlink(iw):
    cp = ConfigParser()
    cp.read(path+"/list.cfg")
    section = cp.sections()[0]
    return (cp.get(section, iw))


def iwalllink():
    links = []
    for x in iwlist():
        links.append(iwlink(x))
    return links