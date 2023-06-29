import os

import toml
from os.path import abspath

from core.exceptions import ConfigFileNotFound

config_filename = 'config.toml'
config_path = abspath('./config/' + config_filename)

old_cfg_file_path = abspath('./config/config.cfg')


def convert_cfg_to_toml():
    import configparser
    config = configparser.ConfigParser()
    config.read(old_cfg_file_path)
    config_dict = {}
    for section in config.sections():
        config_dict[section] = dict(config[section])

    for x in config_dict:
        for y in config_dict[x]:
            if config_dict[x][y] == "True":
                config_dict[x][y] = True
            elif config_dict[x][y] == "False":
                config_dict[x][y] = False
            elif config_dict[x][y].isdigit():
                config_dict[x][y] = int(config_dict[x][y])

    with open(config_path, 'w') as f:
        f.write(toml.dumps(config_dict))
    os.remove(old_cfg_file_path)


class CFG:
    def __init__(self):
        if not os.path.exists(config_path):
            if os.path.exists(old_cfg_file_path):
                convert_cfg_to_toml()
            else:
                raise ConfigFileNotFound(config_path) from None
        self.cp = toml.loads(open(config_path, 'r', encoding='utf-8').read())

    def config(self, q):
        value_s = self.cp.get('secret')
        value_n = self.cp.get('cfg')
        value = value_s.get(q)
        if not value:
            value = value_n.get(q)
        return value


Config = CFG().config
