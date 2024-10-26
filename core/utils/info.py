import importlib
import glob
import os

from core.console.info import client_name as console_client_name, \
                              sender_name_list as console_sender_name, \
                              target_name_list as console_target_name

def get_bot_names(attribute_name, console_name):
    names = []
    for info_file in glob.glob('./bots/*/info.py'):
        module_name = os.path.splitext(os.path.relpath(info_file, './'))[0].replace('/', '.')
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, attribute_name):
                names.extend(getattr(module, attribute_name) if isinstance(getattr(module, attribute_name), list) else [getattr(module, attribute_name)])
        except Exception:
            continue
    names.append(console_name)
    return names

def get_all_clients_name():
    return get_bot_names('client_name', console_client_name)

def get_all_sender_name():
    return get_bot_names('sender_name_list', console_sender_name)

def get_all_target_name():
    return get_bot_names('target_name_list', console_target_name)

class Info:
    version = None
    subprocess = False
    binary_mode = False
    command_parsed = 0
    client_name = ''

__all__ = ["get_all_clients_name", "get_all_sender_name", "get_all_target_name", "Info"]