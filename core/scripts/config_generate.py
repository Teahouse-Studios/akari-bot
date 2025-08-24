import importlib
import os
import pkgutil
import shutil
import sys
from time import sleep

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants import *
from core.i18n import Locale, load_locale_file
from core.utils.message import isint


def generate_config(dir_path, language):
    load_locale_file()

    config_code_list = {}
    os.makedirs(dir_path, exist_ok=True)
    path_ = os.path.join(dir_path, config_filename)

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
        f.close()
    import bots
    from core.config import CFGManager
    CFGManager.switch_config_path(dir_path)
    CFGManager.load()
    for subm in pkgutil.iter_modules(bots.__path__):
        submodule_name = bots.__name__ + "." + subm.name
        CFGManager.load()
        importlib.import_module(f"{submodule_name}.config")
        CFGManager.save()
        sleep(0.1)
    import core.config.config_base  # noqa
    sleep(1)
    import core.config_webrender  # noqa
    from core.loader import load_modules
    load_modules()


if not os.path.exists(os.path.join(config_path, config_filename)) and __name__ != "__main__":
    try:
        print("Hi, it seems you are first time to run AkariBot, what language do you want to use by default?")
        print("".join([f"{i}. {lang_list[list(lang_list.keys())[i - 1]]}\n" for i in range(1, len(lang_list) + 1)]))
        while True:
            lang = input("Please input the number of the language you want to use: ")
            if lang.strip() == "":
                sys.exit(0)
            if isint(lang) and (langI := int(lang) - 1) in range(len(lang_list)):
                lang = list(lang_list.keys())[langI]
                break
            print("Invalid input, please try again.")

        generate_config(config_path, lang)

        sleep(1)
        print("Config file generated successfully, please modify the config file according to your needs.")
        print(f"The config file is located at \"{config_path}\"")
        print("Please restart the bot after modifying the config file.")
        print("Press enter to exit.")
        input()
        sys.exit(0)
    except Exception:
        print()
        sys.exit(1)


if __name__ == "__main__":

    cfg_file_path = os.path.join(config_path, config_filename)
    old_cfg_file_path = os.path.join(config_path, "config.cfg")
    if not os.path.exists(cfg_file_path):
        if os.path.exists(old_cfg_file_path):
            pass
        else:
            os.makedirs(config_path, exist_ok=True)
            open(cfg_file_path, "w", encoding="utf-8").close()
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

    base_import_lists = list(sys.modules)

    def clear_import_cache():
        for m in list(sys.modules):
            if m not in base_import_lists:
                del sys.modules[m]

    for lang in lang_list:
        config_store_path_ = os.path.join(config_store_path, lang)
        os.makedirs(config_store_path_, exist_ok=True)
        generate_config(config_store_path_, lang)
        clear_import_cache()
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
