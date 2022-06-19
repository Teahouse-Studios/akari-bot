import os
import sys

from config import Config

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path"\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above example directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')

import asyncio
import traceback
import aioconsole
import logging

from datetime import datetime

from bot import init_bot, TimedPatternFileHandler
from core.elements import MsgInfo, Session, PrivateAssets, EnableDirtyWordCheck
from core.console.template import Template as MessageSession, FetchTarget
from core.parser.message import parser
from core.utils import init, init_async
from core.logger import Logger

EnableDirtyWordCheck.status = True
PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
init()


async def console_scheduler():
    await init_async(FetchTarget)


async def console_command():
    try:
        m = await aioconsole.ainput('> ')
        await send_command(m)
        await console_command()
    except KeyboardInterrupt:
        print('Exited.')
        exit()
    except Exception:
        Logger.error(traceback.format_exc())


async def send_command(msg):
    time = datetime.now()
    Logger.info('-------Start-------')
    await parser(MessageSession(target=MsgInfo(targetId='TEST|0',
                                               senderId='TEST|0',
                                               senderName='',
                                               targetFrom='TEST|Console',
                                               senderFrom='TEST|Console', clientName='TEST'),
                                session=Session(message=msg, target='TEST|0', sender='TEST|0')))
    Logger.info('----Process end----')
    usage_time = datetime.now() - time
    Logger.info('Usage time:' + str(usage_time))


async def autotest():
    test_file = './test_commands.txt'
    if not os.path.exists(test_file):
        Logger.error('Test file not found.')
    read = open(test_file, 'r', encoding='utf-8')
    commands = read.read().split('\n\n')
    for command in commands:
        await send_command(command)


if __name__ == '__main__':
    logger = logging.getLogger()
    logpath = os.path.abspath('./logs')
    logger.addHandler(TimedPatternFileHandler('{}_%Y-%m-%d.log'.format(logpath + '/console_log'), mode='a', backup_count=5))
    init_bot()
    loop = asyncio.get_event_loop()
    argv = sys.argv
    autotest_ = False
    if len(argv) > 1:
        if argv[1] == 'autotest':
            autotest_ = True
    if not autotest_:
        loop.create_task(console_scheduler())
        loop.create_task(console_command())
        loop.run_forever()
    else:
        loop.create_task(autotest())
        loop.run_forever()
