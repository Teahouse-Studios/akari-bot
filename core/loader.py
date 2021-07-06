import importlib
import os
import re
import traceback

from graia.application.logger import LoggingLogger
from .elements import Plugin

DisplayAttributeError = False
err_prompt = []


def logger_info(msg):
    LoggingLogger().info(msg)


class PluginManager:
    _plugin_list = set()

    @classmethod
    def add_plugin(cls, plugin: Plugin):
        PluginManager._plugin_list.add(plugin)

    @classmethod
    def return_as_dict(cls):
        d = {}
        for x in PluginManager._plugin_list:
            d.update({x.name: x.function})
        return d


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
        other_function = {
            'admin': dict,
            'essential': dict,
            'help': dict,
            'rss': dict,
            'alias': dict
        }
        functions = {}
        functions.update(modules_function)
        functions.update(other_function)
        functions_list = {}
        functions_list['modules_function'] = []
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
                if file_name != '__pycache__':
                    fun_file = file_name
                else:
                    continue
            if os.path.isfile(file_path):
                b = re.match(r'(.*)(.py)', file_path)
                if b:
                    fun_file = b.group(1)
                else:
                    continue
            if fun_file is not None:
                logger_info('Loading modules.' + fun_file + '...')
                modules = 'modules.' + fun_file
                importlib.import_module(modules)
        functions_list["modules_function"] = PluginManager.return_as_dict()
        logger_info(f'Now we have function = {functions_list["modules_function"]}')
        return functions_list


Modules = ModulesLoader().load_modules()

loadercache = os.path.abspath('.cache_loader')
openloadercache = open(loadercache, 'w')
if err_prompt:
    err_prompt = re.sub('  File "<frozen importlib.*?>", .*?\n', '', '\n'.join(err_prompt))
    openloadercache.write('加载模块中发生了以下错误，对应模块未加载：\n' + err_prompt)
else:
    openloadercache.write('所有模块已正确加载。')
openloadercache.close()