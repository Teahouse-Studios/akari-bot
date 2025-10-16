import importlib
import os
import multiprocessing
import pkgutil
import shutil
import sys
from pathlib import Path
from time import sleep

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants import *
from core.i18n import Locale, load_locale_file
from core.utils.message import is_int


def generate_config(dir_path: Path, language: str):
    load_locale_file()

    dir_path.mkdir(parents=True, exist_ok=True)
    path_ = dir_path / config_filename

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
    from core.config import CFGManager
    CFGManager.switch_config_path(dir_path)
    CFGManager.load()
    import core.config.base  # noqa
    import bots
    for subm in pkgutil.iter_modules(bots.__path__):
        module_py_name = f"{bots.__name__}.{subm.name}"
        try:
            CFGManager.load()
            importlib.import_module(f"{module_py_name}.config")
            CFGManager.save()
            sleep(0.1)
        except Exception:
            continue
    import modules
    for subm in pkgutil.iter_modules(modules.__path__):
        module_py_name = f"{modules.__name__}.{subm.name}"
        try:
            CFGManager.load()
            importlib.import_module(f"{module_py_name}.config")
            CFGManager.save()
            sleep(0.1)
        except Exception:
            continue


if not (config_path / config_filename).exists() and __name__ != "__main__":
    try:
        print("Hi, it seems you are first time to run AkariBot, what language do you want to use by default?")
        print("".join([f"{i}. {lang_list[list(lang_list.keys())[i - 1]]}\n" for i in range(1, len(lang_list) + 1)]))
        while True:
            lang = input("Please input the number of the language you want to use: ")
            if lang.strip() == "":
                sys.exit(0)
            if is_int(lang) and (langI := int(lang) - 1) in range(len(lang_list)):
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
    multiprocessing.set_start_method("spawn", force=True)

    cfg_file_path = config_path / config_filename
    old_cfg_file_path = config_path / "config.cfg"
    if not cfg_file_path.exists():
        if old_cfg_file_path.exists():
            pass
        else:
            config_path.mkdir(parents=True, exist_ok=True)
            open(cfg_file_path, "w", encoding="utf-8").close()
    import zipfile
    import difflib

    def zip_language_folders(config_store_path: Path, config_store_packed_path):
        for lang in [c.name for c in config_store_path.iterdir()]:
            lang_path = config_store_path / lang
            if lang_path.is_dir():
                zip_path = config_store_packed_path / f"{lang}.zip"
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    lang_path_obj = Path(lang_path)

                    for file_path in lang_path_obj.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(lang_path_obj)
                            zipf.write(file_path, arcname)

    config_store_path = assets_path / "config_store"
    config_store_packed_path = assets_path / "config_store_packed"
    config_store_path_bak = assets_path / "config_store_bak"

    attempt = 1
    success = False
    while attempt <= 3 and not success:
        if config_store_path_bak.exists():
            shutil.rmtree(config_store_path_bak)
        if config_store_path.exists():
            shutil.move(config_store_path, config_store_path_bak)
        config_store_path.mkdir(parents=True, exist_ok=True)
        config_store_packed_path.mkdir(parents=True, exist_ok=True)

        processes = []
        for lang in lang_list:
            config_store_path_ = config_store_path / lang
            config_store_path_.mkdir(parents=True, exist_ok=True)
            p = multiprocessing.Process(target=generate_config, args=(config_store_path_, lang))
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

        for lang in lang_list:
            config_file = config_store_path / lang / config_filename
            if not config_file.exists():
                break
            with open(config_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "[config]" not in content:
                    break
        else:
            success = True

        if success:
            break

        print(
            f"Error: Some {config_filename} files are missing [config] section. Rolling back to previous config files.")
        if config_store_path.exists():
            shutil.rmtree(config_store_path)
        if config_store_path_bak.exists():
            shutil.move(config_store_path_bak, config_store_path)
        print(f"Rollback completed. Attempt {attempt}...")
        attempt += 1
        sleep(1)
    else:
        print("Failed after 3 attempts. Exiting.")
        sys.exit(1)

    repack = False
    for lang in lang_list:
        config_store_path_ = config_store_path / lang
        config_store_path_bak_ = config_store_path_bak / lang
        if not config_store_path_bak_.exists():
            repack = True
            break
        for file_path in config_store_path_.rglob('*'):
            if file_path.is_file():
                file_path_bak = config_store_path_bak_ / file_path.relative_to(config_store_path_)
                if not file_path_bak.exists():
                    repack = True
                    break

                with open(file_path, "r", encoding="utf-8") as f:
                    new = f.readlines()
                with open(file_path_bak, "r", encoding="utf-8") as f:
                    old = f.readlines()

                diff = difflib.unified_diff(old, new, fromfile=str(file_path_bak), tofile=str(file_path))
                for d in diff:
                    if d:
                        repack = True
                        break

                if repack:
                    break

    if repack:
        zip_language_folders(config_store_path, config_store_packed_path)
        print("Changes detected, repacked the config files.")
    shutil.rmtree(config_store_path_bak)

    print("Config files generated successfully.")
