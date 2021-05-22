import traceback
from configparser import ConfigParser
from os.path import abspath

config_filename = 'config.cfg'
config_path = abspath('./config/' + config_filename)


class CFG:
    def config(self, q):
        cp = ConfigParser()
        cp.read(config_path)
        try:
            section = cp.sections()[0]
            value = cp.get(section, q)
        except Exception:
            traceback.print_exc()
            return False
        if value.upper() == 'TRUE':
            return True
        if value.upper() == 'FALSE':
            return False
        return value


Config = CFG().config
