import os
from os.path import abspath
from typing import Union, Any, get_origin, get_args

from loguru import logger
import toml

from core.exceptions import ConfigFileNotFound, ConfigValueError
from core.utils.text import isfloat, isint


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
            elif isint(config_dict[x][y]):
                config_dict[x][y] = int(config_dict[x][y])
            elif isfloat(config_dict[x][y]):
                config_dict[x][y] = float(config_dict[x][y])

    with open(config_path, 'w') as f:
        f.write(toml.dumps(config_dict))
    os.remove(old_cfg_file_path)


class CFG:
    value = None
    _ts = None

    @classmethod
    def load(cls):
        if not os.path.exists(config_path):
            if os.path.exists(old_cfg_file_path):
                convert_cfg_to_toml()
            else:
                raise ConfigFileNotFound(config_path) from None
        try:
            cls.value = toml.loads(open(config_path, 'r', encoding='utf-8').read())
        except Exception as e:
            raise ConfigValueError(e)
        cls._ts = os.path.getmtime(config_path)

    @classmethod
    def get(cls, q: str, default: Union[Any, None] = None, cfg_type: Union[type, tuple, None] = None) -> Any:
        q = q.lower()
        if os.path.getmtime(config_path) != cls._ts:
            cls.load()
        value_s = cls.value.get('secret')
        value_n = cls.value.get('cfg')
        value = value_s.get(q)
        if value is None:
            value = value_n.get(q)
        if value is None and default is not None:
            return default
        if cfg_type:
            if isinstance(cfg_type, type) or isinstance(cfg_type, tuple):
                if isinstance(cfg_type, tuple):
                    cfg_type_str = ', '.join(map(lambda t: t.__name__, cfg_type))
                    if value is not None and not isinstance(value, cfg_type):
                        logger.warning(f'[Config] Config {q} has a wrong type, expected {
                                       cfg_type_str}, got {type(value).__name__}.')
                else:
                    if value is not None and not isinstance(value, cfg_type):
                        logger.warning(
                            f'[Config] Config {q} has a wrong type, expected {
                                cfg_type.__name__}, got {
                                type(value).__name__}.')
            else:
                logger.warning(f'[Config] Invalid cfg_type provided in config {
                               q}. cfg_type should be a type or a tuple of types.')
        elif default:
            if not isinstance(value, type(default)):
                logger.warning(
                    f'[Config] Config {q} has a wrong type, expected {
                        type(default).__name__}, got {
                        type(value).__name__}.')
                return default
        return value

    @classmethod
    def write(cls, q: str, value: Union[Any, None], secret: bool = False):
        q = q.lower()
        if os.path.getmtime(config_path) != cls._ts:
            cls.load()
        value_s = cls.value.get('secret')
        value_n = cls.value.get('cfg')
        if q in value_s:
            value_s[q] = value
        elif q in value_n:
            value_n[q] = value
        else:
            if secret:
                value_s[q] = value
            else:
                value_n[q] = value
        cls.value['secret'] = value_s
        cls.value['cfg'] = value_n
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(toml.dumps(cls.value))
        cls.load()

    @classmethod
    def delete(cls, q: str) -> bool:
        q = q.lower()
        if os.path.getmtime(config_path) != cls._ts:
            cls.load()
        value_s = cls.value.get('secret')
        value_n = cls.value.get('cfg')
        if q in value_s:
            del value_s[q]
        elif q in value_n:
            del value_n[q]
        else:
            return False
        cls.value['secret'] = value_s
        cls.value['cfg'] = value_n
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(toml.dumps(cls.value))
        cls.load()
        return True

    @classmethod
    def get_url(cls, q: str, default: Union[str, None] = None) -> Union[str, None]:
        q = cls.get(q, default, str)
        if q:
            if q[-1] != '/':
                q += '/'
        return q


CFG.load()
Config = CFG.get
