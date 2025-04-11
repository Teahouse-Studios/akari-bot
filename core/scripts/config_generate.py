import os
import re
import shutil
import sys
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
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                        if f := match_code.finditer(code):  # Find all Config() functions in the code
                            for m in f:
                                left_brackets_count = 0
                                param_text = ""
                                for param in code[m.end(
                                ):]:  # Get the parameters text inside the Config() function by counting brackets
                                    if param == "(":
                                        left_brackets_count += 1
                                    elif param == ")":
                                        left_brackets_count -= 1
                                    if left_brackets_count == -1:
                                        break
                                    param_text += param
                                config_code_list[param_text] = file_path
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
    for c in config_code_list:
        spl = c.split(",") + ["_generate=True"]  # Add _generate=True param to the end of the config function
        for s in spl:
            if s.strip() == "":
                spl.remove(s)
        try:
            # Execute the code to generate the config file, yeah, just stupid but works
            exec(f"Config({",".join(spl)})")  # noqa
        except (NameError, TypeError):
            # traceback.print_exc()
            ...

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


if __name__ == "__main__":
    import zipfile
    import difflib

    def zip_language_folders(config_store_path, config_store_packed_path):
        for lang in os.listdir(config_store_path):
            lang_path = os.path.join(config_store_path, lang)
            if os.path.isdir(lang_path):
                zip_path = os.path.join(config_store_packed_path, f"{lang}.zip")
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for root, _, files in os.walk(lang_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, lang_path)
                            zipf.write(file_path, arcname)

    config_store_path = os.path.join(assets_path, "config_store")
    config_store_packed_path = os.path.join(assets_path, "config_store_packed")
    config_store_path_bak = config_store_path + "_bak"
    if os.path.exists(config_store_path_bak):
        shutil.rmtree(config_store_path_bak)
    if os.path.exists(config_store_path):
        shutil.move(config_store_path, config_store_path_bak)
    os.makedirs(config_store_path, exist_ok=True)
    os.makedirs(config_store_packed_path, exist_ok=True)
    for lang in lang_list:
        config_store_path_ = os.path.join(config_store_path, lang)
        os.makedirs(config_store_path_, exist_ok=True)
        generate_config(config_store_path_, lang)
    # compare old and new config files
    repack = False
    for lang in lang_list:
        config_store_path_ = os.path.join(config_store_path, lang)
        config_store_path_bak = config_store_path + "_bak"
        if not os.path.exists(config_store_path_bak):
            repack = True
            break
        for root, _, files_ in os.walk(config_store_path_):
            for file in files_:
                file_path = os.path.join(root, file)
                file_path_bak = file_path.replace(config_store_path, config_store_path_bak)
                if not os.path.exists(file_path_bak):
                    repack = True
                    break
                with open(file_path, "r", encoding="utf-8") as f:
                    new = f.readlines()
                with open(file_path_bak, "r", encoding="utf-8") as f:
                    old = f.readlines()
                diff = difflib.unified_diff(old, new, fromfile=file_path_bak, tofile=file_path)
                for d in diff:

                    if d:
                        print(d)
                        repack = True
                        break
            if repack:
                break
    if repack:
        zip_language_folders(config_store_path, config_store_packed_path)
        print("Changes detected, repacked the config files.")
    shutil.rmtree(config_store_path + "_bak")

    print("Config files generated successfully.")
