from config import Config

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path"\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above example directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')


import asyncio
import traceback
import os
import shutil

from core.elements.message import MsgInfo, Session
from core.unit_test.template import Template
from core.parser.message import parser
from core.loader import Modules

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

async def unit_test():
    while True:
        try:
            m = input('> ')
            await parser(Template(target=MsgInfo(targetId='TEST|0',
                                                       senderId='TEST|0',
                                                       senderName='',
                                                       targetFrom='TEST|Console',
                                                       senderFrom='TEST|Console'),
                                        session=Session(message=m, target='TEST|0', sender='TEST|0')))
            print('----Process end----')
        except KeyboardInterrupt:
            print('Exited.')
            break
        except Exception:
            traceback.print_exc()

asyncio.run(unit_test())
