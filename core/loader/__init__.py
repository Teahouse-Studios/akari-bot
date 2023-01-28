import importlib
import os
import re
import sys
import traceback
from typing import Dict, Union

from core.elements import Command, Schedule, RegexCommand, StartUp, PrivateAssets
from core.logger import Logger

load_dir_path = os.path.abspath('./modules/')


def load_modules():
    err_prompt = []
    fun_file = None
    dir_list = os.listdir(load_dir_path)
    for file_name in dir_list:
        try:
            file_path = os.path.join(load_dir_path, file_name)
            fun_file = None
            if os.path.isdir(file_path):
                if file_name[0] != '_':
                    fun_file = file_name
            elif os.path.isfile(file_path):
                if file_name[0] != '_' and file_name.endswith('.py'):
                    fun_file = file_name[:-3]
            if fun_file is not None:
                Logger.info(f'Loading modules.{fun_file}...')
                modules = 'modules.' + fun_file
                importlib.import_module(modules)
                Logger.info(f'Succeeded loaded modules.{fun_file}!')
        except:
            tb = traceback.format_exc()
            errmsg = f'Failed to load modules.{fun_file}: \n{tb}'
            Logger.error(errmsg)
            err_prompt.append(errmsg)
    loadercache = os.path.abspath(PrivateAssets.path + '/.cache_loader')
    openloadercache = open(loadercache, 'w')
    if err_prompt:
        err_prompt = re.sub(r'  File \"<frozen importlib.*?>\", .*?\n', '', '\n'.join(err_prompt))
        openloadercache.write(err_prompt)
    else:
        openloadercache.write('')
    openloadercache.close()


class ModulesManager:
    modules: Dict[str, Union[Command, Schedule, RegexCommand, StartUp]] = {}
    modulesOrigin: Dict[str, str] = {}

    @staticmethod
    def add_module(module: Union[Command, Schedule, RegexCommand, StartUp], py_module_name: str):
        if module.bind_prefix not in ModulesManager.modules:
            ModulesManager.modules.update({module.bind_prefix: module})
            ModulesManager.modulesOrigin.update({module.bind_prefix: py_module_name})
        else:
            raise ValueError(f'Duplicate bind prefix "{module.bind_prefix}"')

    @staticmethod
    def remove_modules(modules):
        for module in modules:
            if module in ModulesManager.modules:
                Logger.info(f'Removing...{module}')
                ModulesManager.modules.pop(module)
                ModulesManager.modulesOrigin.pop(module)
            else:
                raise ValueError(f'Module "{module}" is not exist')

    @staticmethod
    def search_related_module(module, includeSelf=True):
        if module in ModulesManager.modulesOrigin:
            modules = []
            py_module = ModulesManager.return_py_module(module)
            for m in ModulesManager.modulesOrigin:
                if ModulesManager.modulesOrigin[m].startswith(py_module):
                    modules.append(m)
            if not includeSelf:
                modules.remove(module)
            return modules
        else:
            raise ValueError(f'Could not find "{module}" in modulesOrigin dict')

    @staticmethod
    def return_py_module(module):
        if module in ModulesManager.modulesOrigin:
            return re.match(r'^modules(\.[a-zA-Z0-9_]*)?', ModulesManager.modulesOrigin[module]).group()
        else:
            return None

    @staticmethod
    def bind_to_module(bind_prefix: str, meta):
        if bind_prefix in ModulesManager.modules:
            ModulesManager.modules[bind_prefix].match_list.add(meta)

    @staticmethod
    def return_modules_list_as_dict(targetFrom: str = None) -> \
        Dict[str, Union[Command, RegexCommand, Schedule, StartUp]]:
        if targetFrom is not None:
            returns = {}
            for m in ModulesManager.modules:
                if isinstance(ModulesManager.modules[m], (Command, RegexCommand, Schedule, StartUp)):
                    if targetFrom in ModulesManager.modules[m].exclude_from:
                        continue
                    available = ModulesManager.modules[m].available_for
                    if targetFrom in available or '*' in available:
                        returns.update({m: ModulesManager.modules[m]})
            return returns
        return ModulesManager.modules

    @staticmethod
    def return_modules_alias_map() -> Dict[str, str]:
        """
        返回每个别名映射到的模块
        """
        modules = ModulesManager.return_modules_list_as_dict()
        alias_map = {}
        for m in modules:
            module = modules[m]
            if module.alias is not None:
                alias_map.update(module.alias)
        return alias_map

    @staticmethod
    def return_module_alias(module_name) -> Dict[str, str]:
        """
        返回此模块的别名列表
        """
        module = ModulesManager.return_modules_list_as_dict()[module_name]
        if module.alias is None:
            return {}
        return module.alias

    @staticmethod
    def return_modules_developers_map() -> Dict[str, list]:
        d = {}
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if module.developers is not None:
                d.update({m: module.developers})
        return d

    @staticmethod
    def return_specified_type_modules(module_type: [Command, RegexCommand, Schedule, StartUp],
                                      targetFrom: str = None) \
        -> Dict[str, Union[Command, RegexCommand, Schedule, StartUp]]:
        d = {}
        modules = ModulesManager.return_modules_list_as_dict()
        for m in modules:
            module = modules[m]
            if isinstance(module, module_type):
                if targetFrom is not None:
                    if isinstance(module, (Command, RegexCommand, Schedule, StartUp)):
                        if targetFrom in module.exclude_from:
                            continue
                        if targetFrom in module.available_for or '*' in module.available_for:
                            d.update({m: module})
                else:
                    d.update({module.bind_prefix: module})
        return d

    @staticmethod
    def reload_module(module_name: str):
        """
        重载该小可模块（以及该模块所在文件的其它模块）
        """
        py_module = ModulesManager.return_py_module(module_name)
        unbind_modules = ModulesManager.search_related_module(module_name)
        ModulesManager.remove_modules(unbind_modules)
        return ModulesManager.reload_py_module(py_module)

    @staticmethod
    def reload_py_module(module_name: str):
        """
        重载该py模块
        """
        try:
            Logger.info(f'Reloading {module_name} ...')
            module = sys.modules[module_name]
            cnt = 0
            loadedModList = list(sys.modules.keys())
            for mod in loadedModList:
                if mod.startswith(f'{module_name}.'):
                    cnt += ModulesManager.reload_py_module(mod)
            importlib.reload(module)
            Logger.info(f'Succeeded reloaded {module_name}')
            return cnt + 1
        except:
            tb = traceback.format_exc()
            errmsg = f'Failed to reload {module_name}: \n{tb}'
            Logger.error(errmsg)
            return -999
