import importlib
import os
import re
import traceback
from os.path import abspath

from graia.application.logger import LoggingLogger


display_load_err = False


def logger_info(msg):
    LoggingLogger().info(msg)


def find_modules_logger(kwargs):
    if isinstance(kwargs, dict):
        for x in kwargs:
            logger_info(f'Find {x}: {kwargs[x]}, update to list.')
    if isinstance(kwargs, list):
        for x in kwargs:
            logger_info(f'Find {x}, update to list.')


def command_loader(reload=False):
    fun_file = None
    admin_list = {}
    essential_list = {}
    command_list = {}
    help_list = {}
    regex_list = {}
    self_options_list = []
    options_list = []
    load_dir_path = os.path.abspath('./modules/')
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        file_path = f'{load_dir_path}/{file_name}'
        if os.path.isdir(file_path):
            if file_path != '__pycache__':
                fun_file = file_name
        if os.path.isfile(file_path):
            b = re.match(r'(.*)(.py)', file_path)
            if b:
                fun_file = b.group(1)
        try:
            if fun_file is not None:
                logger_info('Loading modules.' + fun_file + '...')
                import_fun = importlib.__import__('modules.' + fun_file, fromlist=[fun_file])
                if reload:
                    importlib.reload(import_fun)
                try:
                    admins = import_fun.admin
                    if isinstance(admins, dict):
                        admin_list.update(admins)
                        find_modules_logger(admins)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    essentials = import_fun.essential
                    if isinstance(essentials, dict):
                        essential_list.update(essentials)
                        find_modules_logger(essentials)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    fun_commands = import_fun.command
                    if isinstance(fun_commands, dict):
                        command_list.update(fun_commands)
                        find_modules_logger(fun_commands)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    fun_help = import_fun.help
                    if isinstance(fun_help, dict):
                        help_list.update(fun_help)
                        find_modules_logger(fun_help)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    fun_regex = import_fun.regex
                    if isinstance(fun_regex, dict):
                        regex_list.update(fun_regex)
                        find_modules_logger(fun_regex)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    fun_self_options = import_fun.self_options
                    if isinstance(fun_self_options, list):
                        for x in fun_self_options:
                            self_options_list.append(x)
                        find_modules_logger(fun_self_options)
                except:
                    if display_load_err:
                        traceback.print_exc()
                try:
                    fun_options = import_fun.options
                    if isinstance(fun_options, list):
                        for x in fun_options:
                            self_options_list.append(x)
                        find_modules_logger(fun_options)
                except:
                    if display_load_err:
                        traceback.print_exc()
        except:
            if display_load_err:
                traceback.print_exc()
    return admin_list, essential_list, command_list, help_list, regex_list, self_options_list, options_list


def rss_loader():
    fun_file = None
    rss_list = {}
    load_dir_path = os.path.abspath('./modules/')
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        file_path = f'{load_dir_path}/{file_name}'
        if os.path.isdir(file_path):
            if file_path != '__pycache__':
                fun_file = file_name
        if os.path.isfile(file_path):
            b = re.match(r'(.*)(.py)', file_path)
            if b:
                fun_file = b.group(1)
        try:
            if fun_file is not None:
                import_fun = importlib.__import__('modules.' + fun_file, fromlist=[fun_file])
                try:
                    rss = import_fun.rss
                    if isinstance(rss, dict):
                        rss_list.update(rss)
                        find_modules_logger(rss)
                except:
                    if display_load_err:
                        traceback.print_exc()
        except:
            if display_load_err:
                traceback.print_exc()
    return rss_list
