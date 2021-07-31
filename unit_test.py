from config import Config

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path"\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above configuration directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')


import asyncio
import traceback

from core.elements.message import MessageSession, MsgInfo, Session
from core.unit_test.template import Template
from core.parser.message import parser
from core.loader import Modules


MessageSession.bind_template(Template)


async def unit_test():
    while True:
        try:
            m = input('> ')
            await parser(MessageSession(target=MsgInfo(targetId='TEST|0',
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
