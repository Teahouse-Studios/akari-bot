import shutil
from pathlib import Path

PACKAGES_DIR = Path("packages")


def copy_plugins(import_parent: str, member_prefix: str, target: Path) -> None:
    for member in sorted(PACKAGES_DIR.glob(f"{member_prefix}*")):
        source = member / "src" / import_parent
        if not source.is_dir():
            continue
        for plugin in sorted(source.iterdir()):
            if plugin.is_dir():
                shutil.copytree(plugin, target / plugin.name)


if __name__ == "__main__":
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    shutil.copytree("assets", output_dir / "assets")
    shutil.copytree("assets/config_store/zh_cn", output_dir / "config")
    if Path("data").exists():
        shutil.copytree("data", output_dir / "data")
    else:
        (output_dir / "data").mkdir(exist_ok=True)
    copy_plugins("bots", "akari-bot-adapter-", output_dir / "bots")
    shutil.copytree(PACKAGES_DIR / "akari-bot-core" / "src" / "core" / "locales", output_dir / "core" / "locales")
    copy_plugins("modules", "akari-bot-module-", output_dir / "modules")

    build_paths = [Path("wrapper-build")]
    for build_path in build_paths:
        if build_path.exists():
            for file in build_path.iterdir():
                if file.suffix in [".exe", ".bin", ".app"]:
                    shutil.copyfile(file, output_dir / file.name)

    (output_dir / "database").mkdir(exist_ok=True)
