import importlib
import os
import re
import traceback

from graia.application.logger import LoggingLogger

DisplayAttributeError = False


def logger_info(msg):
    LoggingLogger().info(msg)


class ModulesLoader:
    def __init__(self):
        pass

    def load_modules(self):
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
            'help': dict,
            'rss': dict
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
                    fun_file = None
            if os.path.isfile(file_path):
                b = re.match(r'(.*)(.py)', file_path)
                if b:
                    fun_file = b.group(1)
            try:
                if fun_file is not None:
                    logger_info('Loading modules.' + fun_file + '...')
                    modules = 'modules.' + fun_file
                    import_fun = importlib.__import__(modules, fromlist=[fun_file])
                    for x in functions:
                        try:
                            attrs = import_fun.__getattribute__(x)
                            if attrs:
                                if functions[x] == dict:
                                    if isinstance(attrs, dict):
                                        functions_list[x].update(attrs)
                                        logger_info(
                                            f'Successfully loaded to {x} list from {modules} module: ' + str(attrs))
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
                                            logger_info(
                                                f'Successfully loaded to {x} list from {modules} module: ' + str(y))
                                            if x in modules_function:
                                                functions_list['modules_function'].append(y)
                                            if x in friend_modules_function:
                                                functions_list['friend_modules_function'].append(y)
                                    else:
                                        logger_info(f'?? wtf {x} in {fun_file} format is wrong! should be list.')
                        except AttributeError as e:
                            if DisplayAttributeError:
                                logger_info(str(e))
            except:
                traceback.print_exc()
        functions_list["modules_function"] = list(set(functions_list["modules_function"]))
        functions_list["friend_modules_function"] = list(set(functions_list["friend_modules_function"]))
        logger_info(f'Now we have function = {functions_list["modules_function"]}')
        logger_info(f'Now we have friend function = {functions_list["friend_modules_function"]}')
        return functions_list


Modules = ModulesLoader().load_modules()
