import importlib
import os
import re
import traceback


def command_loader():
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
        print(file_path)
        if os.path.isdir(file_path):
            if file_path != '__pycache__':
                fun_file = file_name
        if os.path.isfile(file_path):
            b = re.match(r'(.*)(.py)', file_path)
            if b:
                fun_file = b.group(1)
        print(fun_file)
        try:
            if fun_file is not None:
                import_fun = importlib.__import__('modules.' + fun_file, fromlist=[fun_file])
                try:
                    admins = import_fun.admin
                    if isinstance(admins, dict):
                        admin_list.update(admins)
                        print(admins)
                except:
                    traceback.print_exc()
                try:
                    essentials = import_fun.essential
                    if isinstance(essentials, dict):
                        essential_list.update(essentials)
                        print(essentials)
                except:
                    traceback.print_exc()
                try:
                    fun_commands = import_fun.command
                    if isinstance(fun_commands, dict):
                        command_list.update(fun_commands)
                        print(fun_commands)
                except:
                    traceback.print_exc()
                try:
                    fun_help = import_fun.help
                    if isinstance(fun_help, dict):
                        help_list.update(fun_help)
                        print(fun_help)
                except:
                    traceback.print_exc()
                try:
                    fun_regex = import_fun.regex
                    if isinstance(fun_regex, dict):
                        regex_list.update(fun_regex)
                        print(fun_regex)
                except:
                    traceback.print_exc()
                try:
                    fun_self_options = import_fun.self_options
                    if isinstance(fun_self_options, list):
                        for x in fun_self_options:
                            self_options_list.append(x)
                        print(fun_self_options)
                except:
                    traceback.print_exc()
                try:
                    fun_options = import_fun.options
                    if isinstance(fun_options, list):
                        for x in fun_options:
                            self_options_list.append(x)
                        print(fun_options)
                except:
                    traceback.print_exc()
        except:
            traceback.print_exc()
    return admin_list, essential_list, command_list, help_list, regex_list, self_options_list, options_list


def rss_loader():
    fun_file = None
    rss_list = {}
    load_dir_path = os.path.abspath('./modules/')
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        file_path = f'{load_dir_path}/{file_name}'
        print(file_path)
        if os.path.isdir(file_path):
            if file_path != '__pycache__':
                fun_file = file_name
        if os.path.isfile(file_path):
            b = re.match(r'(.*)(.py)', file_path)
            if b:
                fun_file = b.group(1)
        print(fun_file)
        try:
            if fun_file is not None:
                import_fun = importlib.__import__('modules.' + fun_file, fromlist=[fun_file])
                try:
                    rss = import_fun.rss
                    if isinstance(rss, dict):
                        rss_list.update(rss)
                        print(rss)
                except:
                    traceback.print_exc()
        except:
            traceback.print_exc()
    return rss_list
