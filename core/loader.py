import importlib
import os
import re
import traceback

from .logger import Logger
from .elements import Plugin

err_prompt = []


def load_modules():
    fun_file = None
    load_dir_path = os.path.abspath('./modules/')
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        try:
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
                Logger.info(f'Loading modules.{fun_file}...')
                modules = 'modules.' + fun_file
                importlib.import_module(modules)
                Logger.info(f'Succeeded loaded modules.{fun_file}!')
        except:
            tb = traceback.format_exc()
            Logger.info(f'Failed to load modules.{fun_file}: {tb}')
            err_prompt.append(str(tb))

class PluginManager:
    _plugin_list = set()

    @classmethod
    def add_plugin(cls, plugin: Plugin):
        PluginManager._plugin_list.add(plugin)

    @classmethod
    def return_plugin_list(cls):
        return PluginManager._plugin_list

    @classmethod
    def return_plugin_as_dict(cls):
        return {x.bind_prefix: x for x in PluginManager._plugin_list}

    @classmethod
    def return_plugin_alias_map(cls):
        alias_map = {}
        for x in PluginManager._plugin_list:
            if isinstance(x.alias, str):
                alias_map.update({x.alias: x.bind_prefix})
            if isinstance(x.alias, tuple):
                for y in x.alias:
                    alias_map.update({y: x.bind_prefix})
        return alias_map


load_modules()
Modules = PluginManager.return_plugin_as_dict()
ModulesAliases = PluginManager.return_plugin_alias_map()


loadercache = os.path.abspath('.cache_loader')
openloadercache = open(loadercache, 'w')
if err_prompt:
    err_prompt = re.sub('  File "<frozen importlib.*?>", .*?\n', '', '\n'.join(err_prompt))
    openloadercache.write('加载模块中发生了以下错误，对应模块未加载：\n' + err_prompt)
else:
    openloadercache.write('所有模块已正确加载。')
openloadercache.close()