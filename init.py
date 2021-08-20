import os
import shutil


def init_bot():
    cache_path = os.path.abspath('./cache/')
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        os.mkdir(cache_path)
    else:
        os.mkdir(cache_path)

    version = os.path.abspath('.version')
    write_version = open(version, 'w')
    write_version.write(os.popen('git rev-parse HEAD', 'r').read()[0:7])
    write_version.close()

    tag = os.path.abspath('.version_tag')
    write_tag = open(tag, 'w')
    write_tag.write(os.popen('git tag -l', 'r').read().split('\n')[-2])
    write_tag.close()
