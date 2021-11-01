import os

from config import Config

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path"\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above example directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')

import asyncio
import traceback
import aioconsole

from init import init_bot
from core.elements import Schedule, StartUp, MsgInfo, Session, PrivateAssets, EnableDirtyWordCheck
from core.unit_test.template import Template as MessageSession, FetchTarget
from core.parser.message import parser
from core.scheduler import Scheduler
from core.loader import ModulesManager
from core.utils import init

EnableDirtyWordCheck.status = True
PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()


async def unit_test_scheduler():
    gather_list = []
    Modules = ModulesManager.return_modules_list_as_dict()
    for x in Modules:
        if isinstance(Modules[x], StartUp):
            gather_list.append(asyncio.ensure_future(Modules[x].function(FetchTarget)))
        if isinstance(Modules[x], Schedule):
            Scheduler.add_job(func=Modules[x].function, trigger=Modules[x].trigger, args=[FetchTarget])
    await asyncio.gather(*gather_list)
    Scheduler.start()


async def unit_test_command():
    try:
        m = await aioconsole.ainput('> ')
        await parser(MessageSession(target=MsgInfo(targetId='TEST|0',
                                                   senderId='TEST|0',
                                                   senderName='',
                                                   targetFrom='TEST|Console',
                                                   senderFrom='TEST|Console'),
                                    session=Session(message=m, target='TEST|0', sender='TEST|0')))
        print('----Process end----')
        await unit_test_command()
    except KeyboardInterrupt:
        print('Exited.')
        exit()
    except Exception:
        traceback.print_exc()


init_bot()
loop = asyncio.get_event_loop()
loop.create_task(unit_test_scheduler())
loop.create_task(unit_test_command())
loop.run_forever()
