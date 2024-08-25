import shutil
import os

if __name__ == "__main__":
    os.mkdir('output')
    shutil.copytree('assets', 'output/assets')
    os.mkdir('output/config')
    shutil.copyfile('config/config.toml.example', 'output/config/config.toml.example')
    shutil.copytree('locales', 'output/locales')
    shutil.copytree('modules', 'output/modules')

    def remove_py_files(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                if (file.endswith('.py') or file.endswith('.pyc') or file.endswith('.pyo') or file.endswith('.pyd') or
                        file.endswith('.pyw')):
                    os.remove(os.path.join(root, file))

        for root, dirs, files in os.walk(path):
            for dir in dirs:
                if dir == '__pycache__':
                    shutil.rmtree(os.path.join(root, dir))
    remove_py_files('output/modules')

    # copy builds from build folder

    if os.path.exists('build'):
        for root, dirs, files in os.walk('build'):
            for file in files:
                if file.endswith('.exe'):
                    shutil.copyfile(os.path.join(root, file), os.path.join('output', file))
                elif file.endswith('.bin'):
                    shutil.copyfile(os.path.join(root, file), os.path.join('output', file))
                elif file.endswith('.app'):
                    shutil.copytree(os.path.join(root, file), os.path.join('output', file))

    if os.path.exists('wrapper-build'):
        for root, dirs, files in os.walk('wrapper-build'):
            for file in files:
                if file.endswith('.exe'):
                    shutil.copyfile(os.path.join(root, file), os.path.join('output', file))
                elif file.endswith('bot.bin'):
                    shutil.copyfile(os.path.join(root, file), os.path.join('output', file))
                elif file.endswith('bot.app'):
                    shutil.copytree(os.path.join(root, file), os.path.join('output', file))
