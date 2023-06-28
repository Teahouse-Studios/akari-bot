from configparser import ConfigParser
from os.path import abspath

from core.exceptions import ConfigFileNotFound

config_filename = 'config.cfg'
config_path = abspath('./config/' + config_filename)


class CFG:
    def __init__(self):
        self.cp = ConfigParser()
        self.cp.read(config_path)

    def config(self, q):
        section = self.cp.sections()

        if len(section) == 0:
            raise ConfigFileNotFound(config_path) from None
        value = self.cp.get('secret', q, fallback=False)
        if not value:
            value = self.cp.get('cfg', q, fallback=False)
        if not value:
            return None
        if value.upper() == 'TRUE':
            return True
        if value.upper() in ['', 'FALSE']:
            return False
        return value


Config = CFG().config
CachePath = Config('cache_path')
DBPath = Config('db_path')
