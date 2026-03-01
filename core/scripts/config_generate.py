"""
配置文件生成脚本。

该脚本的功能：
1. 首次运行时自动生成配置文件框架
2. 扫描所有机器人和模块，为其生成配置项
3. 支持多语言配置生成
4. 使用多进程并行生成各语言配置，提高效率
5. 自动检测并重新生成有变化的配置
6. 配置文件打包为zip格式便于分发

主要用途：
- 初始化时自动生成默认配置
- 添加新模块后更新配置文件
- 支持多语言配置的生成和维护
"""

import importlib
import multiprocessing
import os
import pkgutil
import shutil
import sys
import traceback
from pathlib import Path
from time import sleep

if __name__ == "__main__":
    sys.path.append(os.getcwd())

from core.constants import *
from core.i18n import Locale, load_locale_file
from core.utils.func import is_int


def generate_config(dir_path: Path, language: str):
    """为指定语言生成配置文件。

    该函数会：
    1. 加载本地化文件
    2. 创建目录和空的配置文件
    3. 写入配置文件头注释和默认配置
    4. 扫描所有机器人和模块配置，自动加载并生成配置项

    :param dir_path: 配置文件保存的目录路径
    :param language: 语言代码（如"zh_cn"、"en_us"等）
    """
    # 加载本地化语言文件
    load_locale_file()

    # 创建目录（如果不存在则创建，包括父目录）
    dir_path.mkdir(parents=True, exist_ok=True)
    path_ = dir_path / config_filename

    # 创建空的配置文件并写入文件头
    locale = Locale(language)
    with open(path_, "w", encoding="utf-8") as f:
        # 从本地化文件中读取配置文件头说明（多行注释）
        f.write(f"# {locale.t('config.header.line.1', fallback_failed_prompt=False)}\n")
        f.write(f"# {locale.t('config.header.line.2', fallback_failed_prompt=False)}\n")
        f.write(f"# {locale.t('config.header.line.3', fallback_failed_prompt=False)}\n")
        f.write("\n")
        # 写入默认语言配置
        f.write(
            f'default_locale = "{language}" # {
                locale.t("config.comments.default_locale", fallback_failed_prompt=False)
            }\n'
        )
        # 写入配置版本信息，用于版本兼容性检查
        f.write(
            f"config_version = {str(config_version)} # {
                locale.t('config.comments.config_version', fallback_failed_prompt=False)
            }\n"
        )
        f.close()

    # 导入配置管理器
    from core.config import CFGManager

    # 切换配置管理器的路径到指定目录
    CFGManager.switch_config_path(dir_path)
    CFGManager.load()

    # 导入核心配置模块，触发其配置生成
    import core.config.base  # noqa

    # 导入所有机器人包
    import bots

    # 遍历bots目录下的所有子模块
    for subm in pkgutil.iter_modules(bots.__path__):
        module_py_name = f"{bots.__name__}.{subm.name}"
        try:
            # 加载该机器人的配置模块，会自动触发配置生成
            CFGManager.load()
            importlib.import_module(f"{module_py_name}.config")
            CFGManager.save()
            # 稍微延迟，避免过快的文件操作
            sleep(0.1)
        except ModuleNotFoundError:
            # 如果该机器人没有配置模块，则跳过
            continue
        except Exception:
            # 捕获其他异常并继续处理下一个模块
            traceback.print_exc()
            continue

    # 导入所有模块包
    import modules

    # 遍历modules目录下的所有子模块
    for subm in pkgutil.iter_modules(modules.__path__):
        module_py_name = f"{modules.__name__}.{subm.name}"
        try:
            # 加载该模块的配置，会自动触发配置生成
            CFGManager.load()
            importlib.import_module(f"{module_py_name}.config")
            CFGManager.save()
            # 稍微延迟，避免过快的文件操作
            sleep(0.1)
        except ModuleNotFoundError:
            # 如果该模块没有配置，则跳过
            continue
        except Exception:
            # 捕获其他异常并继续处理下一个模块
            traceback.print_exc()
            continue


# 检查是否是首次运行（配置文件不存在且当前不是作为主程序运行时）
if not (config_path / config_filename).exists() and __name__ != "__main__":
    try:
        # 交互式询问用户选择默认语言
        print("Hi, it seems you are first time to run AkariBot, what language do you want to use by default?")
        # 显示所有可用语言选项
        print("".join([f"{i}. {lang_list[list(lang_list.keys())[i - 1]]}\n" for i in range(1, len(lang_list) + 1)]))

        # 循环等待用户输入有效的语言选择
        while True:
            lang = input("Please input the number of the language you want to use: ")
            # 如果用户输入为空，则退出
            if lang.strip() == "":
                sys.exit(0)
            # 检查输入是否为有效的数字，且在语言列表范围内
            if is_int(lang) and (langI := int(lang) - 1) in range(len(lang_list)):
                # 将用户选择的数字转换为语言代码
                lang = list(lang_list.keys())[langI]
                break
            print("Invalid input, please try again.")

        # 调用配置生成函数，为选定的语言生成配置文件
        generate_config(config_path, lang)

        # 等待1秒后显示成功提示
        sleep(1)
        print("Config file generated successfully, please modify the config file according to your needs.")
        print(f'The config file is located at "{config_path}"')
        print("Please restart the bot after modifying the config file.")
        print("Press enter to exit.")
        input()
        sys.exit(0)
    except Exception:
        print()
        sys.exit(1)


# 主程序入口：用于批量生成所有语言的配置文件
if __name__ == "__main__":
    # 设置多进程启动方法为'spawn'，确保跨平台兼容性
    # 这是必要的，因为某些平台的默认方法可能不兼容
    multiprocessing.set_start_method("spawn", force=True)

    # 定义主配置文件路径
    cfg_file_path = config_path / config_filename
    # 定义旧格式配置文件路径（向后兼容）
    old_cfg_file_path = config_path / "config.cfg"

    # 检查新格式配置文件是否存在
    if not cfg_file_path.exists():
        # 如果旧格式配置文件存在，则跳过（保持向后兼容）
        if old_cfg_file_path.exists():
            pass
        else:
            # 创建配置目录并生成空的配置文件
            config_path.mkdir(parents=True, exist_ok=True)
            open(cfg_file_path, "w", encoding="utf-8").close()

    # 导入zip文件处理和文件差异比较模块
    import zipfile
    import difflib

    def zip_language_folders(config_store_path: Path, config_store_packed_path):
        """将各语言的配置文件夹打包为 zip 文件。

        将每个语言的配置目录压缩为单个 zip 文件，便于分发和备份。

        :param config_store_path: 配置存储根目录（包含各语言子目录）
        :param config_store_packed_path: 压缩文件的输出目录
        """
        # 遍历配置目录下的所有语言文件夹
        for lang in [c.name for c in config_store_path.iterdir()]:
            lang_path = config_store_path / lang
            # 只处理目录，跳过文件
            if lang_path.is_dir():
                # 为该语言创建对应的zip文件
                zip_path = config_store_packed_path / f"{lang}.zip"
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    lang_path_obj = Path(lang_path)

                    # 递归遍历语言目录中的所有文件
                    for file_path in lang_path_obj.rglob("*"):
                        if file_path.is_file():
                            # 保存相对路径到zip文件中
                            arcname = file_path.relative_to(lang_path_obj)
                            zipf.write(file_path, arcname)

    # 定义配置存储路径
    config_store_path = assets_path / "config_store"
    # 定义压缩配置文件的输出路径
    config_store_packed_path = assets_path / "config_store_packed"
    # 定义备份路径（用于失败时的恢复）
    config_store_path_bak = assets_path / "config_store_bak"

    # 最多尝试 3 次生成配置，如果失败则回滚
    attempt = 1
    success = False
    while attempt <= 3 and not success:
        # 删除旧备份（如果存在）
        if config_store_path_bak.exists():
            shutil.rmtree(config_store_path_bak)

        # 将当前配置目录备份（如果存在）
        if config_store_path.exists():
            shutil.move(config_store_path, config_store_path_bak)

        # 创建新的配置和压缩文件目录
        config_store_path.mkdir(parents=True, exist_ok=True)
        config_store_packed_path.mkdir(parents=True, exist_ok=True)

        # 使用多进程并行生成各语言的配置文件
        processes = []
        for lang in lang_list:
            config_store_path_ = config_store_path / lang
            config_store_path_.mkdir(parents=True, exist_ok=True)
            # 为每种语言创建一个进程
            p = multiprocessing.Process(target=generate_config, args=(config_store_path_, lang))
            p.start()
            processes.append(p)

        # 等待所有进程完成
        for p in processes:
            p.join()

        # 检查所有配置文件是否都成功生成
        for lang in lang_list:
            config_file = config_store_path / lang / config_filename
            # 检查配置文件是否存在
            if not config_file.exists():
                break
            # 检查主配置文件是否包含 `[config]` 部分（标志配置成功）
            with open(config_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "[config]" not in content:
                    break
        else:
            # 所有配置文件都有效，标记成功
            success = True

        if success:
            break

        # 生成失败，进行回滚
        print(
            f"Error: Some {config_filename} files are missing [config] section. Rolling back to previous config files."
        )
        if config_store_path.exists():
            shutil.rmtree(config_store_path)
        if config_store_path_bak.exists():
            shutil.move(config_store_path_bak, config_store_path)
        print(f"Rollback completed. Attempt {attempt}...")
        attempt += 1
        sleep(1)
    else:
        # 3 次尝试都失败，退出程序
        print("Failed after 3 attempts. Exiting.")
        sys.exit(1)

    # 判断是否需要重新打包配置文件
    repack = False
    # 对比新生成的配置文件和备份文件
    for lang in lang_list:
        config_store_path_ = config_store_path / lang
        config_store_path_bak_ = config_store_path_bak / lang
        # 如果备份不存在，则需要打包
        if not config_store_path_bak_.exists():
            repack = True
            break
        # 遍历新配置文件目录中的所有文件
        for file_path in config_store_path_.rglob("*"):
            if file_path.is_file():
                # 获取对应的备份文件路径
                file_path_bak = config_store_path_bak_ / file_path.relative_to(config_store_path_)
                # 如果备份文件不存在，则需要打包
                if not file_path_bak.exists():
                    repack = True
                    break

                # 对比新旧文件内容
                with open(file_path, "r", encoding="utf-8") as f:
                    new = f.readlines()
                with open(file_path_bak, "r", encoding="utf-8") as f:
                    old = f.readlines()

                # 使用difflib检测文件差异
                diff = difflib.unified_diff(old, new, fromfile=str(file_path_bak), tofile=str(file_path))
                # 如果有任何差异，则需要打包
                for d in diff:
                    if d:
                        repack = True
                        break

                if repack:
                    break

    # 如果检测到变化，则重新打包所有配置文件
    if repack:
        zip_language_folders(config_store_path, config_store_packed_path)
        print("Changes detected, repacked the config files.")

    # 删除备份目录
    shutil.rmtree(config_store_path_bak)

    print("Config files generated successfully.")
