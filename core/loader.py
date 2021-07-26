import importlib
import os
import re
import traceback

from .logger import Logger
from core.elements import Module

err_prompt = []

load_dir_path = os.path.abspath('./modules/')


def load_modules():
    fun_file = None
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        try:
            file_path = f'{load_dir_path}/{file_name}'
            fun_file = None
            if os.path.isdir(file_path):
                if file_name != '__pycache__':
                    fun_file = file_name
            if fun_file is not None:
                Logger.info(f'Loading modules.{fun_file}...')
                modules = 'modules.' + fun_file
                importlib.import_module(modules)
                Logger.info(f'Succeeded loaded modules.{fun_file}!')
        except:
            tb = traceback.format_exc()
            Logger.info(f'Failed to load modules.{fun_file}: \n{tb}')
            err_prompt.append(str(tb))

class ModulesManager:
    _modules_list = set()

    @classmethod
    def add_module(cls, module: Module):
        ModulesManager._modules_list.add(module)

    @classmethod
    def return_modules_list(cls):
        return ModulesManager._modules_list

    @classmethod
    def return_modules_list_as_dict(cls):
        return {x.bind_prefix: x for x in ModulesManager._modules_list}

    @classmethod
    def return_modules_alias_map(cls):
        alias_map = {}
        for x in ModulesManager._modules_list:
            if isinstance(x.alias, str):
                alias_map.update({x.alias: x.bind_prefix})
            if isinstance(x.alias, tuple):
                for y in x.alias:
                    alias_map.update({y: x.bind_prefix})
            if isinstance(x.alias, dict):
                alias_map.update(x.alias)
        return alias_map

    @classmethod
    def return_regex_modules(cls):
        d = {}
        for x in ModulesManager._modules_list:
            if x.is_regex_function:
                d.update({x.bind_prefix: x})
        return d


load_modules()
Modules = ModulesManager.return_modules_list_as_dict()
ModulesAliases = ModulesManager.return_modules_alias_map()
ModulesRegex = ModulesManager.return_regex_modules()


loadercache = os.path.abspath('.cache_loader')
openloadercache = open(loadercache, 'w')
if err_prompt:
    err_prompt = re.sub('  File "<frozen importlib.*?>", .*?\n', '', '\n'.join(err_prompt))
    openloadercache.write('加载模块中发生了以下错误，对应模块未加载：\n' + err_prompt)
else:
    openloadercache.write('所有模块已正确加载。')
openloadercache.close()