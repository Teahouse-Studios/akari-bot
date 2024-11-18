import os
import re

from time import sleep

from core.path import config_path

config_filename = 'config.toml'

cfg_file_path = os.path.join(config_path, config_filename)

if not os.path.exists(cfg_file_path):
    while True:
        lang_list = ['zh_cn', 'zh_tw', 'en_us']
        lang = input(
            """Hello, it seems you are first time to run Akari-bot, what language do you want to use by default?
    1. zh_cn (简体中文)
    2. zh_tw (繁體中文)
    3. en_us (English)
    Please input the number of the language you want to use:""")
        if lang in ['1', '2', '3']:
            lang = lang_list[int(lang) - 1]
            break
        else:
            print('Invalid input, please try again.')

    import traceback
    from tomlkit import dumps
    from core.utils.text import random_string  # noqa

    config_code_list = []

    dir_list = ['bots', 'core', 'modules', 'schedulers']
    exclude_dir_list = [os.path.join('core', 'config'), os.path.join('core', 'scripts')]

    match_code = re.compile(r'(config\()', re.DOTALL)

    # create empty config.toml

    with open(cfg_file_path, 'w', encoding='utf-8') as f:
        f.write('default_locale = "' + lang + '"')
        f.close()

    from core.config import config, CFGManager  # noqa
    from core.config.update import config_version

    CFGManager.value.add('config_version', config_version)

    for dir in dir_list:
        for root, dirs, files in os.walk(dir):
            if root in exclude_dir_list:
                continue
            for file in files:
                if file.endswith('.py'):
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        code = f.read()
                        if f := match_code.finditer(code):
                            for m in f:
                                left_brackets_count = 0
                                param_text = ''
                                for param in code[m.end():]:
                                    if param == '(':
                                        left_brackets_count += 1
                                    elif param == ')':
                                        left_brackets_count -= 1
                                    if left_brackets_count == -1:
                                        break
                                    param_text += param
                                config_code_list.append(param_text)

    for c in config_code_list:
        if c.endswith(','):
            c = c[:-1]
        c += ', _generate=True'  # Add _generate=True to the end of the config function
        try:
            eval(f'config({c})')  # Execute the code to generate the config file
        except NameError:
            traceback.print_exc()

    with open(cfg_file_path, 'w', encoding='utf-8') as f:
        f.write(dumps(CFGManager.value))
        f.close()

    sleep(1)
    print('Config file generated successfully, please modify the config file according to your needs.')
    print('The config file is located at ' + cfg_file_path)
    print('Please restart the bot after modifying the config file.')
    print('Press any key to exit.')
    input()
    exit(0)
