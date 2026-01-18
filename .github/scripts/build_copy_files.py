import shutil
from pathlib import Path

if __name__ == "__main__":
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    shutil.copytree("assets", output_dir / "assets")
    shutil.copytree("assets/config_store/zh_cn", output_dir / "config")
    shutil.copytree("bots", output_dir / "bots")
    shutil.copytree("core/locales", output_dir / "core" / "locales")
    shutil.copytree("modules", output_dir / "modules")

    def remove_py_files(path: Path):
        for file in path.rglob("*"):
            if file.suffix in [".py", ".pyc", ".pyo", ".pyd", ".pyw"]:
                file.unlink()

        for pycache in path.rglob("__pycache__"):
            if pycache.is_dir():
                shutil.rmtree(pycache)

    remove_py_files(output_dir / "modules")

    build_paths = [Path("wrapper-build")]
    for build_path in build_paths:
        if build_path.exists():
            for file in build_path.iterdir():
                if file.suffix in [".exe", ".bin", ".app"]:
                    shutil.copyfile(file, output_dir / file.name)

    (output_dir / "database").mkdir(exist_ok=True)
