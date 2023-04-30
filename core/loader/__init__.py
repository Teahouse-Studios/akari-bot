import importlib
import os
import re
import sys
import traceback
from typing import Dict, Union

from core.builtins import PrivateAssets
from core.logger import Logger
from core.types import Module
from core.types.module.component_meta import CommandMeta, RegexMeta, ScheduleMeta
from core.utils.i18n import load_locale_file

load_dir_path = os.path.abspath('./modules/')


def load_modules():
    err_prompt = []
    locale_err = load_locale_file()
    if locale_err:
        locale_err.append('i18n:')
        err_prompt.append('\n'.join(locale_err))
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
        except BaseException:
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

    modules = ModulesManager.modules
    for m in modules:
        module = modules[m]
        if module.alias:
            ModulesManager.modules_aliases.update(module.alias)


class ModulesManager:
    modules: Dict[str, Module] = {}
    modules_aliases: Dict[str, str] = {}
    modules_origin: Dict[str, str] = {}

    @staticmethod
    def add_module(module: Module, py_module_name: str):
        if module.bind_prefix not in ModulesManager.modules:
            ModulesManager.modules.update({module.bind_prefix: module})
            ModulesManager.modules_origin.update({module.bind_prefix: py_module_name})
        else:
            raise ValueError(f'Duplicate bind prefix "{module.bind_prefix}"')

    @staticmethod
    def remove_modules(modules):
        for module in modules:
            if module in ModulesManager.modules:
                Logger.info(f'Removing...{module}')
                ModulesManager.modules.pop(module)
                ModulesManager.modules_origin.pop(module)
            else:
                raise ValueError(f'Module "{module}" is not exist')

    @staticmethod
    def search_related_module(module, includeSelf=True):
        if module in ModulesManager.modules_origin:
            modules = []
            py_module = ModulesManager.return_py_module(module)
            for m in ModulesManager.modules_origin:
                if ModulesManager.modules_origin[m].startswith(py_module):
                    modules.append(m)
            if not includeSelf:
                modules.remove(module)
            return modules
        else:
            raise ValueError(f'Could not find "{module}" in modules_origin dict')

    @staticmethod
    def return_py_module(module):
        if module in ModulesManager.modules_origin:
            return re.match(r'^modules(\.[a-zA-Z0-9_]*)?', ModulesManager.modules_origin[module]).group()
        else:
            return None

    @staticmethod
    def bind_to_module(bind_prefix: str, meta: Union[CommandMeta, RegexMeta, ScheduleMeta]):
        if bind_prefix in ModulesManager.modules:
            if isinstance(meta, CommandMeta):
                ModulesManager.modules[bind_prefix].command_list.add(meta)
            elif isinstance(meta, RegexMeta):
                ModulesManager.modules[bind_prefix].regex_list.add(meta)
            elif isinstance(meta, ScheduleMeta):
                ModulesManager.modules[bind_prefix].schedule_list.add(meta)

    @staticmethod
    def return_modules_list(targetFrom: str = None) -> \
            Dict[str, Module]:
        if targetFrom is not None:
            returns = {}
            for m in ModulesManager.modules:
                if isinstance(ModulesManager.modules[m], Module):
                    if targetFrom in ModulesManager.modules[m].exclude_from:
                        continue
                    available = ModulesManager.modules[m].available_for
                    if targetFrom in available or '*' in available:
                        returns.update({m: ModulesManager.modules[m]})
            return returns
        return ModulesManager.modules

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
        except BaseException:
            tb = traceback.format_exc()
            errmsg = f'Failed to reload {module_name}: \n{tb}'
            Logger.error(errmsg)
            return -999
