import asyncio
import os
import shutil

from core.bots import run

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

run()
