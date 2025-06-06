import os
import re
import shutil
import sys
from importlib import util as importlib_util
from time import sleep

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants import *
from core.i18n import Locale
from core.utils.text import isint


def generate_config(dir_path, language):
    config_code_list = {}
    os.makedirs(dir_path, exist_ok=True)
    path_ = os.path.join(dir_path, config_filename)

    dir_list = ["bots", "core", "modules", "schedulers"]
    exclude_dir_list = [os.path.join("core", "config"), os.path.join("core", "scripts")]

    match_code = re.compile(r"(Config\()", re.DOTALL)

    # create empty config.toml
    locale = Locale(language)
    with open(path_, "w", encoding="utf-8") as f:
        f.write(f"# {locale.t("config.header.line.1", fallback_failed_prompt=False)}\n")
        f.write(f"# {locale.t("config.header.line.2", fallback_failed_prompt=False)}\n")
        f.write(f"# {locale.t("config.header.line.3", fallback_failed_prompt=False)}\n")
        f.write("\n")
        f.write(
            f"default_locale = \"{language}\" # {
                locale.t(
                    "config.comments.default_locale",
                    fallback_failed_prompt=False)}\n")
        f.write(
            f"config_version = {
                str(config_version)} # {
                locale.t(
                    "config.comments.config_version",
                    fallback_failed_prompt=False)}\n")
        f.write("initialized = false\n")
        f.close()

    from core.config import Config, CFGManager  # noqa

    CFGManager.switch_config_path(dir_path)

    for _dir in dir_list:
        for root, _, _files in os.walk(_dir):
            if root in exclude_dir_list:
                continue
            for file in _files:
                if file.endswith(".py"):
                    module_name = file[:-3]
                    module_path = os.path.join(_dir, file)

                    spec = importlib_util.spec_from_file_location(module_name, module_path)
                    module = importlib_util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    del spec
    # filtered_config_code_map = {}
    # for c in config_code_list:
    #     opt = c.split(",")[0]
    #     if opt not in filtered_config_code_map:
    #         filtered_config_code_map[opt] = c
    #     else:
    #         if len(c) > len(filtered_config_code_map[opt]):
    #             print(f"Conflict found: {filtered_config_code_map[opt]}")
    #             filtered_config_code_map[opt] = c
    # config_code_list = [filtered_config_code_map[c] for c in filtered_config_code_map]

    CFGManager.write("initialized", True)


if not os.path.exists(os.path.join(config_path, config_filename)) and __name__ != "__main__":
    while True:
        i = 1
        lang = input(
            f"""Hi, it seems you are first time to run AkariBot, what language do you want to use by default?
{"".join([f"{i}. {lang_list[list(lang_list.keys())[i - 1]]}\n" for i in range(1, len(lang_list) + 1)])}
Please input the number of the language you want to use: """)
        if lang.strip() == "":
            sys.exit(0)
        if isint(lang) and (langI := int(lang) - 1) in range(len(lang_list)):
            lang = list(lang_list.keys())[langI]
            break
        print("Invalid input, please try again.")

    generate_config(config_path, lang)

    sleep(1)
    print("Config file generated successfully, please modify the config file according to your needs.")
    print("The config file is located at " + config_path)
    print("Please restart the bot after modifying the config file.")
    print("Press enter to exit.")
    input()
    sys.exit(0)
