import os
import shutil
from time import sleep

from loguru import logger
from tomlkit import parse as toml_parser, dumps as toml_dumps, document as toml_document, comment as toml_comment, nl
from tomlkit.exceptions import KeyAlreadyPresent

from core.constants import config_filename, config_version
from core.constants.exceptions import ConfigFileNotFound
from core.constants.path import config_path
from core.utils.i18n import Locale
from core.utils.text import isint, isfloat

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
with open(cfg_file_path, 'r', encoding='utf-8') as cfg_file:
    config = toml_parser(cfg_file.read())

# If config version not exists, regenerate the config file (assumed as
# version 0 to convert old to new format since this is the first time to
# generate the config file for everyone)
if 'initialized' not in config.value:
    if 'config_version' not in config:
        old_config = config
        logger.info('Config version not found, regenerating the config file...')
        shutil.copy(cfg_file_path, cfg_file_path + '.bak')
        configs = {'config': toml_document()}
        get_old_locale = old_config['cfg'].get('locale', 'zh_cn')
        old_locale = Locale(get_old_locale)
        configs['config'].add(toml_comment(old_locale.t('config.header.line.1', fallback_failed_prompt=False)))
        configs['config'].add(toml_comment(old_locale.t('config.header.line.2', fallback_failed_prompt=False)))
        configs['config'].add(toml_comment(old_locale.t('config.header.line.3', fallback_failed_prompt=False)))
        configs['config'].add(nl())

        configs['config'].add('default_locale', get_old_locale)
        configs['config'].item('default_locale').comment(old_locale.t(
            'config.comments.default_locale',
            fallback_failed_prompt=False))

        configs['config'].add('config_version', 0)
        configs['config'].item('config_version').comment(old_locale.t(
            'config.comments.default_locale',
            fallback_failed_prompt=False))
        configs['config'].add('initialized', True)
        configs['config'].add(nl())

        # reorganize some keys

        class Reorganize:
            table = ''

            @classmethod
            def reorganize_bot_key(cls, key, secret=False):
                cfg_name = 'bot_' + cls.table
                c_target = 'secret' if key in old_config['secret'] else 'cfg'
                table = cfg_name + '_secret' if secret else cfg_name

                if key in old_config[c_target]:
                    if cfg_name not in configs:
                        configs[cfg_name] = toml_document()
                        configs[cfg_name].add(
                            toml_comment(
                                old_locale.t(
                                    'config.header.line.1',
                                    fallback_failed_prompt=False)))
                        configs[cfg_name].add(
                            toml_comment(
                                old_locale.t(
                                    'config.header.line.2',
                                    fallback_failed_prompt=False)))
                        configs[cfg_name].add(
                            toml_comment(
                                old_locale.t(
                                    'config.header.line.3',
                                    fallback_failed_prompt=False)))
                    if table not in configs[cfg_name].keys():
                        qk = 'config.table.secret_bot' if table.endswith('_secret') else 'config.table.config_bot'
                        configs[cfg_name].add(nl())
                        configs[cfg_name].add(table, toml_document())
                        configs[cfg_name][table].add(toml_comment(old_locale.t(qk, fallback_failed_prompt=False)))

                    try:
                        configs[cfg_name][table].add(key, old_config[c_target][key])
                    except KeyAlreadyPresent:
                        configs[cfg_name][table][key] = old_config[c_target][key]
                    finally:
                        qc = f'config.comments.{key}'
                        # get the comment for the key from locale
                        localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                        if localed_comment != qc:
                            configs[cfg_name][table].value.item(key).comment(localed_comment)
                    old_config[c_target].pop(key)

            @classmethod
            def bot_add_enabled_flag(cls):
                cfg_name = 'bot_' + cls.table
                if cfg_name not in configs:
                    configs[cfg_name] = toml_document()
                    configs[cfg_name].add(
                        toml_comment(
                            old_locale.t(
                                'config.header.line.1',
                                fallback_failed_prompt=False)))
                    configs[cfg_name].add(
                        toml_comment(
                            old_locale.t(
                                'config.header.line.2',
                                fallback_failed_prompt=False)))
                    configs[cfg_name].add(
                        toml_comment(
                            old_locale.t(
                                'config.header.line.3',
                                fallback_failed_prompt=False)))
                    configs[cfg_name].add(nl())
                    configs[cfg_name].add(cfg_name, toml_document())
                    configs[cfg_name][cfg_name].add(
                        toml_comment(
                            old_locale.t(
                                'config.table.config_bot',
                                fallback_failed_prompt=False)))
                try:
                    configs[cfg_name][cfg_name].add('enable', True)
                except KeyAlreadyPresent:
                    configs[cfg_name][cfg_name]['enable'] = True
                finally:
                    qc = 'config.comments.enable'
                    # get the comment for the key from locale
                    localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                    if localed_comment != qc:
                        configs[cfg_name][cfg_name].value.item('enable').comment(localed_comment)

                if 'disabled_bots' in config['cfg']:
                    if cls.table in config['cfg']['disabled_bots']:
                        configs[cfg_name][cfg_name]['enable'] = False

        # aiocqhttp
        Reorganize.table = 'aiocqhttp'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("qq_account")
        Reorganize.reorganize_bot_key("qq_access_token", True)
        Reorganize.reorganize_bot_key("qq_allow_approve_friend")
        Reorganize.reorganize_bot_key("qq_allow_approve_group_invite")
        Reorganize.reorganize_bot_key("qq_enable_listening_self_message")
        Reorganize.reorganize_bot_key("qq_host")
        Reorganize.reorganize_bot_key("qq_limited_emoji")
        Reorganize.reorganize_bot_key("qq_typing_emoji")

        # aiogram

        Reorganize.table = 'aiogram'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("telegram_token", True)

        # api

        Reorganize.table = 'api'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('api_port')
        Reorganize.reorganize_bot_key('jwt_secret', True)

        # discord

        Reorganize.table = 'discord'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('discord_token', True)

        # kook

        Reorganize.table = 'kook'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('kook_token', True)

        # matrix

        Reorganize.table = 'matrix'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key('matrix_homeserver')
        Reorganize.reorganize_bot_key('matrix_user')
        Reorganize.reorganize_bot_key('matrix_device_id', True)
        Reorganize.reorganize_bot_key('matrix_device_name')
        Reorganize.reorganize_bot_key('matrix_token', True)

        # ntqq

        Reorganize.table = 'qqbot'
        Reorganize.bot_add_enabled_flag()
        Reorganize.reorganize_bot_key("qq_bot_appid")
        Reorganize.reorganize_bot_key("qq_bot_secret", True)
        Reorganize.reorganize_bot_key("qq_private_bot")
        Reorganize.reorganize_bot_key("qq_bot_enable_send_url")

        configs['config'].add('config', toml_document())
        configs['config']['config'].add(toml_comment(old_locale.t('config.table.config')))
        if 'cfg' in config:
            for k, v in config['cfg'].items():
                configs['config']['config'][k] = v
                qc = 'config.comments.' + k
                localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                if localed_comment != qc:
                    configs['config']['config'].value.item(k).comment(localed_comment)
        configs['config'].add(nl())

        configs['config'].add('secret', toml_document())
        configs['config']['secret'].add(toml_comment(old_locale.t('config.table.config')))
        if 'secret' in config:
            for k, v in config['secret'].items():
                configs['config']['secret'][k] = v
                qc = 'config.comments.' + k
                localed_comment = old_locale.t(qc, fallback_failed_prompt=False)
                if localed_comment != qc:
                    configs['config']['secret'].value.item(k).comment(localed_comment)

        if 'locale' in configs['config']['config']:
            configs['config']['config'].pop('locale')
        if 'disabled_bots' in configs['config']['config']:
            configs['config']['config'].pop('disabled_bots')

        for c in configs:
            filename = c
            if not c.endswith('.toml'):
                filename += '.toml'
            with open(os.path.join(config_path, filename), 'w', encoding='utf-8') as f:
                f.write(toml_dumps(configs[c]))
        logger.info('Config file regenerated successfully.')
        sleep(3)
    elif config['config_version'] < config_version:
        logger.info(f'Updating Config file from {config['config_version']} to {config_version}...')
        # if config['config_version'] < 1:
        #     config['config_version'] = 1
        #     with open(cfg_file_path, 'w', encoding='utf-8') as f:
        #         f.write(toml_dumps(config))
        #     config = toml_parser(open(cfg_file_path, 'r', encoding='utf-8').read())

        logger.info('Config file updated successfully.')
        sleep(3)
