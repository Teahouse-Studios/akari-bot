import os
import sys

import asyncio
import traceback
import aioconsole

from bot import init_bot
from config import Config
from core.builtins import PrivateAssets, EnableDirtyWordCheck
from core.console.message import MessageSession
from core.extra.scheduler import load_extra_schedulers
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import init_async
from database import BotDBUtil, session
from database.tables import DBVersion

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path" field\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above example directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')

query_dbver = session.query(DBVersion).first()
if not query_dbver:
    session.add_all([DBVersion(value=str(BotDBUtil.database_version))])
    session.commit()
    query_dbver = session.query(DBVersion).first()

if (current_ver := int(query_dbver.value)) < (target_ver := BotDBUtil.database_version):
    print(f'Updating database from {current_ver} to {target_ver}...')
    from database.update import update_database

    update_database()
    print('Database updated successfully! Please restart the program.')
    sys.exit()

EnableDirtyWordCheck.status = True
PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))


async def console_scheduler():
    load_extra_schedulers()
    await init_async()


async def console_command():
    try:
        m = await aioconsole.ainput('> ')
        asyncio.create_task(console_command())
        await send_command(m)
    except KeyboardInterrupt:
        print('Exited.')
        exit()
    except Exception:
        Logger.error(traceback.format_exc())


async def send_command(msg):
    Logger.info('-------Start-------')
    returns = await parser(MessageSession(target=MsgInfo(target_id='TEST|Console|0',
                                                         sender_id='TEST|0',
                                                         sender_name='',
                                                         target_from='TEST|Console',
                                                         sender_from='TEST', client_name='TEST', message_id=0,
                                                         reply_id=None),
                                          session=Session(message=msg, target='TEST|Console|0', sender='TEST|0')))
    # print(returns)
    Logger.info('----Process end----')
    return returns


if __name__ == '__main__':
    init_bot()
    loop = asyncio.new_event_loop()
    loop.create_task(console_scheduler())
    loop.create_task(console_command())
    loop.run_forever()
