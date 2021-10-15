import importlib
import os
import re
import traceback
from typing import Dict, Union, List, Set

from core.elements import Command, Option, Schedule, RegexCommand, StartUp, PrivateAssets
from core.logger import Logger

load_dir_path = os.path.abspath('./modules/')


def load_modules():
    err_prompt = []
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
    loadercache = os.path.abspath(PrivateAssets.path + '/.cache_loader')
    openloadercache = open(loadercache, 'w')
    if err_prompt:
        err_prompt = re.sub('  File "<frozen importlib.*?>", .*?\n', '', '\n'.join(err_prompt))
        openloadercache.write('加载模块中发生了以下错误，对应模块未加载：\n' + err_prompt)
    else:
        openloadercache.write('所有模块已正确加载。')
    openloadercache.close()


class ModulesManager:
    _modules_list = set()

    @staticmethod
    def add_module(module: [Command, Option, Schedule, RegexCommand, StartUp]):
        ModulesManager._modules_list.add(module)

    @staticmethod
    def return_modules_list() -> Set[Union[Command, RegexCommand, Schedule, StartUp, Option]]:
        return ModulesManager._modules_list

    @staticmethod
    def return_modules_list_as_dict() -> Dict[str, Union[Command, RegexCommand, Schedule, StartUp, Option]]:
        d = {}
        modules = []
        recommend_modules = []
        for alias in ModulesManager.return_modules_alias_map():
            modules.append(alias)
        for x in ModulesManager._modules_list:
            prefix = x.bind_prefix
            if prefix in d:
                raise ValueError(f'Duplicate bind prefix "{prefix}"')
            d.update({prefix: x})
            modules.append(prefix)
            recommend = x.recommend_modules
            if isinstance(recommend, str):
                recommend_modules.append(recommend)
            if isinstance(recommend, (list, tuple)):
                for y in recommend:
                    recommend_modules.append(y)
        for rm in recommend_modules:
            if rm not in modules:
                raise ValueError(f'Invalid recommend module "{rm}"')
        return d

    @staticmethod
    def return_modules_alias_map() -> Dict[str, str]:
        """
        返回每个别名映射到的模块
        """
        alias_map = {}
        for x in ModulesManager._modules_list:
            if isinstance(x.alias, str):
                alias_map.update({x.alias: x.bind_prefix})
            if isinstance(x.alias, dict):
                x.alias = [x.alias]
            if isinstance(x.alias, (tuple, list)):
                for y in x.alias:
                    if isinstance(y, dict):
                        for z in y:
                            alias_map.update({z: y[z]})
                    elif isinstance(y, str):
                        alias_map.update({y: x.bind_prefix})
                    else:
                        raise ValueError(f'Unknown alias elements type: {y}')
        return alias_map

    @staticmethod
    def return_module_alias(module_name) -> Dict[str, list]:
        """
        返回此模块的别名列表
        """
        alias_list = {}
        module = ModulesManager.return_modules_list_as_dict()[module_name]
        if module.alias is None:
            return alias_list
        for x in module.alias:
            if module.bind_prefix not in alias_list:
                alias_list.update({module.bind_prefix: []})
            if isinstance(x, str):
                alias_list[module.bind_prefix].append(x)
            if isinstance(x, dict):
                x = [x]
            if isinstance(x, (tuple, list)):
                for y in x:
                    if isinstance(y, str):
                        alias_list[module.bind_prefix].append(x)
                    if isinstance(y, dict):
                        for z in y:
                            if z not in alias_list:
                                alias_list.update({z: []})
                            alias_list[z].append(y[z])
        return alias_list

    @staticmethod
    def return_modules_developers_map() -> Dict[str, list]:
        d = {}
        for x in ModulesManager._modules_list:
            if x.developers is not None:
                if isinstance(x.developers, str):
                    d.update({x.bind_prefix: [x.developers]})
                elif isinstance(x.developers, (tuple, list)):
                    d.update({x.bind_prefix: x.developers})
        return d

    @staticmethod
    def return_regex_modules() -> Dict[str, RegexCommand]:
        d = {}
        for x in ModulesManager._modules_list:
            if isinstance(x, RegexCommand):
                d.update({x.bind_prefix: x})
        return d

    @staticmethod
    def return_schedule_function_list() -> List[Schedule]:
        l = []
        for x in ModulesManager._modules_list:
            if isinstance(x, Schedule):
                l.append(x)
        return l