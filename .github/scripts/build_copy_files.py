import os
import shutil

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    shutil.copytree("assets", "output/assets")
    shutil.copytree("assets/config_store/zh_cn", "output/config")
    shutil.copytree("core/locales", "output/core/locales")
    shutil.copytree("modules", "output/modules")

    def remove_py_files(path):

        for root, dirs, files in os.walk(path):
            for file in files:
                if (file.endswith(".py") or file.endswith(".pyc") or file.endswith(
                        ".pyo") or file.endswith(".pyd") or file.endswith(".pyw")):
                    os.remove(os.path.join(root, file))

        for root, dirs, files in os.walk(path):
            for dir in dirs:
                if dir == "__pycache__":
                    shutil.rmtree(os.path.join(root, dir))

    remove_py_files("output/modules")

    build_paths = ["wrapper-build"]
    for build_path in build_paths:
        if os.path.exists(build_path):
            for file in os.listdir(build_path):
                if file.endswith(".exe") or file.endswith(".bin") or file.endswith(".app"):
                    shutil.copyfile(os.path.join(build_path, file), os.path.join("output", file))

    os.makedirs("output/database", exist_ok=True)
