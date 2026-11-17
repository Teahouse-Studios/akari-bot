import os
import shutil
from pathlib import Path

# 配置目录的环境变量名。测试引导据此把整个进程指向一份临时配置，
# 从而不依赖、也不改动开发者本机的 config/。
# 该名称在 tester.py 中以字面量重复了一次：此处的取值发生在导入期，
# 而导入 core.constants 本身就会触发取值，引导代码因而无从先行导入本模块取得它。
CONFIG_PATH_ENV = "AKARI_CONFIG_PATH"

# 配置只读模式的环境变量名。守护进程在 spawn bot 与 server 子进程前置位，
# pre-init 进程则清除此标记，以保证配置迁移与缺失项补全只发生在该进程中。
# 该常量须位于不依赖 core.config 的模块，使引导代码能在导入配置系统之前取得它。
CONFIG_READONLY_ENV = "AKARI_CONFIG_READONLY"

# union 合并日志目录的环境变量名。测试引导据此把测试合成的合并记录写进临时目录，
# 不让它们随着每次测试运行堆积在开发者的 data/ 中。
# 与 CONFIG_PATH_ENV 同理，此处的取值发生在导入期，引导代码须先于 core 导入置位，
# 故该名称在 tester.py 与 tests/run_one.py 中各以字面量重复了一次。
UNION_MERGE_LOGS_PATH_ENV = "AKARI_UNION_MERGE_LOGS_PATH"

assets_path = Path("./assets").resolve()
cache_path = Path("./cache").resolve()
config_path = Path(os.environ.get(CONFIG_PATH_ENV) or "./config").resolve()
data_path = Path("./data").resolve()
database_path = Path("./database").resolve()
base_locales_path = Path(__file__).resolve().parent.parent / "locales"
logs_path = Path("./logs").resolve()
tests_path = Path("./tests").resolve()

# assets 与 data 的分工：assets 只放随仓库分发的只读内容，运行时或部署者产生的内容一律写进 data。
data_path.mkdir(parents=True, exist_ok=True)

fonts_path = assets_path / "fonts"
templates_path = assets_path / "templates"

filter_words_path = data_path / "filter_words"
retired_path = data_path / "retired"
union_merge_logs_path = Path(os.environ.get(UNION_MERGE_LOGS_PATH_ENV) or data_path / "union_merge_logs").resolve()
url_audit_data_path = data_path / "url_audit"

noto_sans_bold_path = fonts_path / "Noto Sans CJK Bold.otf"
noto_sans_demilight_path = fonts_path / "Noto Sans CJK DemiLight.otf"
noto_sans_symbol_path = fonts_path / "Noto Sans Symbols2 Regular.ttf"


def find_repo_root(start: Path | None = None) -> Path | None:
    """向上查找包含 .git 的目录；以安装形态部署时返回 None。"""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def collect_locale_paths() -> list[str]:
    """收集 core 与全部插件包的本地化目录，供语言包快照建置使用。"""
    from core.plugin import iter_bot_packages, iter_module_packages

    paths = [str(base_locales_path)]
    for package in (*iter_bot_packages(), *iter_module_packages()):
        if package.locales_path.is_dir():
            paths.append(str(package.locales_path))
    return paths


class PrivateData:
    """客户端私有资源目录，存放需要跨重启保留的运行时文件。"""

    path = data_path / "private" / "default"
    path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def set(cls, path: str | Path):
        path_ = Path(path).resolve()
        path_.mkdir(parents=True, exist_ok=True)
        cls.path = path_


def module_data_path(module_dir: str | Path) -> Path:
    """取模块的可写数据目录，并确保其存在。

    模块以安装形态部署时包目录只读，因此可写数据统一放在 ``data/modules/<模块名>``。
    旧版本写在包目录的 ``data/`` 下，首次访问时迁移过来；迁移失败则继续使用旧位置。

    :param module_dir: 模块根目录，例如 ``Path(__file__).parent``。
    """
    root = Path(module_dir).resolve()
    path = data_path / "modules" / root.name
    legacy = root / "data"
    if legacy.is_dir() and not path.exists():
        try:
            shutil.move(str(legacy), str(path))
        except OSError:
            return legacy
    path.mkdir(parents=True, exist_ok=True)
    return path
