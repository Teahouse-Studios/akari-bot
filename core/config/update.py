import os
import shutil

from time import sleep
from tomlkit import parse as toml_parser, dumps as toml_dumps, document as toml_document, comment as toml_comment, nl
from core.path import config_path

from core.exceptions import ConfigFileNotFound
from core.utils.i18n import Locale
from core.utils.text import isint, isfloat
from loguru import logger

config_version = 0

config_filename = 'config.toml'

cfg_file_path = os.path.join(config_path, config_filename)
old_cfg_file_path = os.path.join(config_path, 'config.cfg')


def convert_cfg_to_toml():
    import configparser
    config_old = configparser.ConfigParser()
    config_old.read(old_cfg_file_path)
    config_dict = {}
    for section in config_old.sections():
        config_dict[section] = {}
        config_dict[section].update(dict(config_old[section]))

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

    with open(cfg_file_path, 'w') as f:
        f.write(toml_dumps(config_dict))
    os.remove(old_cfg_file_path)

# If the config file does not exist, try to convert the old config file to the new format, or raise an error.


if not os.path.exists(cfg_file_path):
    if os.path.exists(old_cfg_file_path):
        convert_cfg_to_toml()
    else:
        raise ConfigFileNotFound(cfg_file_path) from None


# Load the config file

config = toml_parser(open(cfg_file_path, 'r', encoding='utf-8').read())

# If config version not exists, regenerate the config file (assumed as
# version 0 to convert old to new format since this is the first time to
# generate the config file for everyone)
if len(config.value) < 1:
    if 'config_version' not in config:
        logger.warning('Config version not found, regenerating the config file...')
        shutil.copy(cfg_file_path, cfg_file_path + '.bak')
        d = toml_document()
        get_old_locale = config['cfg'].get('locale', 'zh_cn')
        old_locale = Locale(get_old_locale)
        d.add(toml_comment(old_locale.t('config.header.line.1')))
        d.add(toml_comment((old_locale.t('config.header.line.2'))))
        d.add(toml_comment((old_locale.t('config.header.line.3'))))
        d.add(nl())

        d.add(toml_comment((old_locale.t('config.comments.config_version'))))
        d.add('config_version', 0)
        d.add(nl())

        d.add(toml_comment(old_locale.t('config.comments.default_locale')))

        d.add('default_locale', get_old_locale)

        d.add(nl())
        d.add(nl())

        # reorganize some keys



        class Reorganize:
            table = ''

            @classmethod
            def reorganize_bot_key(cls, key):
                table = 'bot_' + cls.table
                if key in config['cfg']:
                    if table not in d:
                        d.add(toml_comment(old_locale.t('config.table.cfg_bot')))
                        d.add(table, toml_document())

                    qc = 'config.comments.' + key
                    localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                    if localed_comment != qc:
                        d[table].add(toml_comment(localed_comment))
                    d[table].add(key, config['cfg'][key])
                    d[table].add(nl())
                    config['cfg'].pop(key)
                if key in config['secret']:
                    table = table + "_secret"
                    if table not in d:
                        d.add(toml_comment(old_locale.t('config.table.secret_bot')))
                        d.add(table, toml_document())
                    qc = 'config.comments.' + key
                    localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                    if localed_comment != qc:
                        d[table].add(toml_comment(localed_comment))
                    d[table].add(key, config['secret'][key])
                    d[table].add(nl())
                    config['secret'].pop(key)

            @classmethod
            def bot_add_enabled_flag(cls):
                table = 'bot_' + cls.table
                if table not in d:
                    d.add(toml_comment(old_locale.t('config.table.cfg_bot')))
                    d.add(table, toml_document())
                qc = 'config.comments.enable'
                localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                if localed_comment != qc:
                    d[table].add(toml_comment(localed_comment))
                d[table].add('enable', True)
                if 'disabled_bots' in config['cfg']:
                    if cls.table in config['cfg']['disabled_bots']:
                        d[table]['enabled'] = False

        # aiocqhttp
        Reorganize.table = 'aiocqhttp'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("qq_account")
        Reorganize.reorganize_bot_key("qq_enable_listening_self_message")
        Reorganize.reorganize_bot_key("qq_allow_approve_friend")
        Reorganize.reorganize_bot_key("qq_allow_approve_group_invite")
        Reorganize.reorganize_bot_key("qq_host")

        d.add(nl())

        # aiogram

        Reorganize.table = 'aiogram'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("telegram_token")

        d.add(nl())

        # api

        Reorganize.table = 'api'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('jwt_secret')
        Reorganize.reorganize_bot_key('api_port')

        d.add(nl())

        # discord

        Reorganize.table = 'discord'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('discord_token')

        d.add(nl())

        # kook

        Reorganize.table = 'kook'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('kook_token')

        d.add(nl())

        # matrix

        Reorganize.table = 'matrix'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('matrix_homeserver')
        Reorganize.reorganize_bot_key('matrix_user')
        Reorganize.reorganize_bot_key('matrix_device_id')
        Reorganize.reorganize_bot_key('matrix_device_name')
        Reorganize.reorganize_bot_key('matrix_token')

        d.add(nl())

        # ntqq

        Reorganize.table = 'ntqq'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("qq_bot_appid")
        Reorganize.reorganize_bot_key("qq_bot_secret")
        Reorganize.reorganize_bot_key("qq_private_bot")
        Reorganize.reorganize_bot_key("qq_bot_enable_send_url")

        d.add(nl())

        d.add(toml_comment(old_locale.t('config.table.secret')))
        d.add('secret', config.value['secret'])
        d.add(nl())
        d.add(nl())

        d.add(toml_comment(old_locale.t('config.table.cfg')))
        d.add('cfg', config.value['cfg'])

        if 'locale' in d['cfg']:
            d['cfg'].pop('locale')
        if 'disabled_bots' in d['cfg']:
            d['cfg'].pop('disabled_bots')

        for t in ['secret', 'cfg']:
            for k in d[t]:
                qc = 'config.comments.' + k
                localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                if localed_comment != qc:
                    d[t].value.item(k).comment(localed_comment)
        with open(cfg_file_path, 'w', encoding='utf-8') as f:
            f.write(toml_dumps(d))
        logger.warning('Config file regenerated successfully.')
        sleep(3)
    elif config['config_version'] < config_version:
        logger.warning(f'Updating Config file from {config['config_version']} to {config_version}...')
        # if config['config_version'] < 1:
        #     config['config_version'] = 1
        #     with open(cfg_file_path, 'w', encoding='utf-8') as f:
        #         f.write(toml_dumps(config))
        #     config = toml_parser(open(cfg_file_path, 'r', encoding='utf-8').read())

        logger.warning('Config file updated successfully.')
        sleep(3)
