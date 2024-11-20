import re
import traceback
from time import sleep

from core.constants import *
from core.utils.i18n import Locale

config_filename = 'config.toml'

cfg_file_path = os.path.join(config_path, config_filename)

if not os.path.exists(cfg_file_path):
    while True:
        i = 1
        lang = input(
            f"""Hello, it seems you are first time to run Akari-bot, what language do you want to use by default?
{''.join([f"{i}. {lang_list[list(lang_list.keys())[i - 1]]}\n" for i in range(1, len(lang_list) + 1)])}
Please input the number of the language you want to use:""")
        if (langI := (int(lang) - 1)) in range(len(lang_list)):
            lang = list(lang_list.keys())[langI]
            break
        else:
            print('Invalid input, please try again.')

    from core.utils.text import random_string  # noqa

    config_code_list = {}

    dir_list = ['bots', 'core', 'modules', 'schedulers']
    exclude_dir_list = [os.path.join('core', 'config'), os.path.join('core', 'scripts')]

    match_code = re.compile(r'(Config\()', re.DOTALL)

    # create empty config.toml

    with open(cfg_file_path, 'w', encoding='utf-8') as f:
        f.write(
            f'default_locale = "{lang}" # {
                Locale(lang).t(
                    'config.comments.default_locale',
                    fallback_failed_prompt=False)}\n')
        f.write(
            f'config_version = {
                str(config_version)} # {
                Locale(lang).t(
                    'config.comments.config_version',
                    fallback_failed_prompt=False)}\n')
        f.write('initialized = false\n')
        f.close()

    from core.config import Config, CFGManager  # noqa

    for dir in dir_list:
        for root, dirs, files in os.walk(dir):
            if root in exclude_dir_list:
                continue
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                        if f := match_code.finditer(code):  # Find all Config() functions in the code
                            for m in f:
                                left_brackets_count = 0
                                param_text = ''
                                for param in code[m.end():]:  # Get the parameters text inside the Config() function by counting brackets
                                    if param == '(':
                                        left_brackets_count += 1
                                    elif param == ')':
                                        left_brackets_count -= 1
                                    if left_brackets_count == -1:
                                        break
                                    param_text += param
                                config_code_list[param_text] = file_path

    for c in config_code_list:
        if c.endswith(','):
            c = c[:-1]
        c += ', _generate=True'  # Add _generate=True param to the end of the config function
        try:
            eval(f'Config({c})')  # Execute the code to generate the config file, yeah, just stupid but works
        except (NameError, TypeError):
            # traceback.print_exc()
            ...

    CFGManager.write('initialized', True)

    sleep(1)
    print('Config file generated successfully, please modify the config file according to your needs.')
    print('The config file is located at ' + cfg_file_path)
    print('Please restart the bot after modifying the config file.')
    print('Press enter to exit.')
    input()
    exit(0)
