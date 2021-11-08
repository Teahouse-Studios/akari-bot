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
    modules: Dict[str, Union[Command, Option, Schedule, RegexCommand, StartUp]] = {}

    @staticmethod
    def add_module(module: [Command, Option, Schedule, RegexCommand, StartUp]):
        if module.bind_prefix not in ModulesManager.modules:
            ModulesManager.modules.update({module.bind_prefix: module})
        else:
            raise ValueError(f'Duplicate bind prefix "{module.bind_prefix}"')

    @staticmethod
    def bind_to_module(bind_prefix: str, meta):
        if bind_prefix in ModulesManager.modules:
            ModulesManager.modules[bind_prefix].match_list.add(meta)

    @staticmethod
    def return_modules_list_as_dict() -> Dict[str, Union[Command, RegexCommand, Schedule, StartUp, Option]]:
        return ModulesManager.modules

    @staticmethod
    def return_modules_alias_map() -> Dict[str, str]:
        """
        返回每个别名映射到的模块
        """
        alias_map = {}
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if isinstance(module.alias, str):
                alias_map.update({module.alias: module.bind_prefix})
            if isinstance(module.alias, dict):
                module.alias = [module.alias]
            if isinstance(module.alias, (tuple, list)):
                for y in module.alias:
                    if isinstance(y, dict):
                        for z in y:
                            alias_map.update({z: y[z]})
                    elif isinstance(y, str):
                        alias_map.update({y: module.bind_prefix})
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
        if isinstance(module.alias, str):
            alias_list.update({module.bind_prefix: [module.alias]})
        if isinstance(module.alias, (list, tuple)):
            for x in module.alias:
                if module.bind_prefix not in alias_list:
                    alias_list.update({module.bind_prefix: []})

                if isinstance(x, dict):
                    x = [x]
                if isinstance(x, (tuple, list)):
                    for y in x:
                        if isinstance(y, str):
                            alias_list[module.bind_prefix].append(y)
                        if isinstance(y, dict):
                            for z in y:
                                if y[z] not in alias_list:
                                    alias_list.update({y[z]: []})
                                alias_list[y[z]].append(z)
        return alias_list

    @staticmethod
    def return_modules_developers_map() -> Dict[str, list]:
        d = {}
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if module.developers is not None:
                if isinstance(module.developers, str):
                    d.update({module.bind_prefix: [module.developers]})
                elif isinstance(module.developers, (tuple, list)):
                    d.update({module.bind_prefix: module.developers})
        return d

    @staticmethod
    def return_regex_modules() -> Dict[str, RegexCommand]:
        d = {}
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if isinstance(module, RegexCommand):
                d.update({module.bind_prefix: module})
        return d

    @staticmethod
    def return_schedule_function_list() -> List[Schedule]:
        l = []
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if isinstance(m, Schedule):
                l.append(m)
        return l
