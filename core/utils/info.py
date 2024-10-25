import importlib
import glob
import os
import traceback

from core.logger import Logger

def get_all_clients_name():
    client_names = []
    for info_file in glob.glob('./bots/*/info.py'):
        module_name = os.path.splitext(os.path.relpath(info_file, './'))[0].replace('/', '.')
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, 'client_name'):
                client_names.append(module.client_name)
        except Exception as e:
            Logger.error(traceback.format_exc(e))

    client_names.append('TEST')
    return client_names


class Info:
    version = None
    subprocess = False
    binary_mode = False
    command_parsed = 0
    client_name = ''
