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

from datetime import datetime

from bot import init_bot
from core.elements import MsgInfo, Session, PrivateAssets, EnableDirtyWordCheck
from core.console.template import Template as MessageSession
from core.parser.message import parser
from core.scheduler import Scheduler
from core.utils import init, init_scheduler
from core.logger import Logger

EnableDirtyWordCheck.status = True
PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()


async def console_scheduler():
    await init_scheduler()


async def console_command():
    try:
        m = await aioconsole.ainput('> ')
        time = datetime.now()
        await parser(MessageSession(target=MsgInfo(targetId='TEST|0',
                                                   senderId='TEST|0',
                                                   senderName='',
                                                   targetFrom='TEST|Console',
                                                   senderFrom='TEST|Console'),
                                    session=Session(message=m, target='TEST|0', sender='TEST|0')))
        print('----Process end----')
        usage_time = datetime.now() - time
        print('Usage time:', usage_time)
        await console_command()
    except KeyboardInterrupt:
        print('Exited.')
        exit()
    except Exception:
        Logger.error(traceback.format_exc())


init_bot()
loop = asyncio.get_event_loop()
loop.create_task(console_scheduler())
loop.create_task(console_command())
loop.run_forever()
