import importlib
import os
import re
import traceback

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


def command_loader():
    fun_file = None
    modules_function = {
    'command': dict,
    'regex': dict,
    'options': list,
    'self_options': list
    }
    friend_modules_function = {
    'friend_options': list
    }
    other_function = {
    'admin': dict,
    'essential': dict,
    'help': dict
    }
    functions = {}
    functions.update(modules_function)
    functions.update(friend_modules_function)
    functions.update(other_function)
    functions_list = {}
    functions_list['modules_function'] = []
    functions_list['friend_modules_function'] = []
    for x in functions:
        if functions[x] == dict:
            functions_list[x] = {}
        if functions[x] == list:
            functions_list[x] = []
    load_dir_path = os.path.abspath('./modules/')
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        file_path = f'{load_dir_path}/{file_name}'
        if os.path.isdir(file_path):
            if file_path != '__pycache__':
                fun_file = file_name
            else:
                continue
        if os.path.isfile(file_path):
            b = re.match(r'(.*)(.py)', file_path)
            if b:
                fun_file = b.group(1)
        try:
            if fun_file is not None:
                logger_info('Loading modules.' + fun_file + '...')
                import_fun = importlib.__import__('modules.' + fun_file, fromlist=[fun_file])
                for x in functions:
                    try:
                        attrs = import_fun.__getattribute__(x)
                        if attrs:
                            if functions[x] == dict:
                                if isinstance(attrs, dict):
                                    functions_list[x].update(attrs)
                                    if x in modules_function:
                                        for y in attrs:
                                            functions_list['modules_function'].append(y)
                                    if x in friend_modules_function:
                                        for y in attrs:
                                            functions_list['friend_modules_function'].append(y)
                                else:
                                    logger_info(f'?? wtf {x} in {fun_file} format is wrong! should be dict.')
                            if functions[x] == list:
                                if isinstance(attrs, list):
                                    for y in attrs:
                                        functions_list[x].append(y)
                                        if x in modules_function:
                                            functions_list['modules_function'].append(y)
                                        if x in friend_modules_function:
                                            functions_list['friend_modules_function'].append(y)
                                else:
                                    logger_info(f'?? wtf {x} in {fun_file} format is wrong! should be list.')
                    except AttributeError as e:
                        logger_info(str(e))
        except:
            traceback.print_exc()
    functions_list["modules_function"] = list(set(functions_list["modules_function"]))
    functions_list["friend_modules_function"] = list(set(functions_list["friend_modules_function"]))
    logger_info(f'Now we have function = {functions_list["modules_function"]}')
    logger_info(f'Now we have friend function = {functions_list["friend_modules_function"]}')
    return functions_list


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
