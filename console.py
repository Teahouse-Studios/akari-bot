import json
import os
import sys

from config import Config

if not Config('db_path'):
    raise AttributeError('Wait! You need to fill a valid database address into the config.cfg "db_path"\n'
                         'Example: \ndb_path = sqlite:///database/save.db\n'
                         '(Also you can fill in the above example directly,'
                         ' bot will automatically create a SQLite database in the "./database/save.db")')

from database import BotDBUtil, session
from database.tables import DBVersion

import asyncio
import traceback
import aioconsole

from bot import init_bot
from core.elements import MsgInfo, AutoSession, PrivateAssets, EnableDirtyWordCheck, Plain
from core.console.template import Template as MessageSession, FetchTarget
from core.parser.message import parser
from core.utils import init, init_async
from core.logger import Logger


query_dbver = session.query(DBVersion).first()
if query_dbver is None:
    session.add_all([DBVersion(value='2')])
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
init()


async def console_scheduler():
    await init_async(FetchTarget)


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


async def send_command(msg, interactions=None):
    Logger.info('-------Start-------')
    returns = await parser(MessageSession(target=MsgInfo(targetId='TEST|Console|0',
                                                         senderId='TEST|0',
                                                         senderName='',
                                                         targetFrom='TEST|Console',
                                                         senderFrom='TEST', clientName='TEST', messageId=0,
                                                         replyId=None),
                                          session=AutoSession(message=msg, target='TEST|Console|0', sender='TEST|0',
                                                              auto_interactions=interactions)))
    # print(returns)
    Logger.info('----Process end----')
    return returns


async def autotest():
    test_file = './test_commands.txt'
    if not os.path.exists(test_file):
        Logger.error('Test file not found.')
    read = open(test_file, 'r', encoding='utf-8')
    commands = read.read().split('\n\n')
    for command in commands:
        sub_c = command.split('\n')
        cmds = ''
        results = {}
        interactions = []
        for sub in sub_c:
            if sub.startswith('~'):
                cmds += sub
            elif sub.startswith('!!results'):
                results = json.loads(sub.replace('!!results=', '', 1))
            elif sub.startswith('!!interactions'):
                interactions = json.loads(sub.replace('!!interactions=', '', 1))
            else:
                cmds += '\n' + sub
            Logger.info(cmds)
        returns = (await send_command(cmds, interactions=interactions)).sent  # todo: 需要收集结果
        included_texts = results.get('include_texts', [])
        excluded_texts = results.get('exclude_texts', [])
        if isinstance(included_texts, str):
            included_texts = [included_texts]
        if isinstance(excluded_texts, str):
            excluded_texts = [excluded_texts]
        for text in included_texts:
            included = False
            for r in returns:
                for rr in r.value:
                    if isinstance(rr, Plain):
                        if rr.text.find(text) != -1:
                            Logger.info('Found included text: ' + text)
                            included = True
            if not included:
                Logger.error('Included text not found: ' + text)
        for text in excluded_texts:
            excluded = False
            for r in returns:
                for rr in r.value:
                    if isinstance(rr, Plain):
                        if rr.text.find(text) != -1:
                            Logger.error('Found excluded text: ' + text)
                            excluded = True
            if not excluded:
                Logger.info('Excluded text not found: ' + text)

        included_elements = results.get('include_elements', [])
        excluded_elements = results.get('exclude_elements', [])
        if isinstance(included_elements, str):
            included_elements = [included_elements]
        if isinstance(excluded_elements, str):
            excluded_elements = [excluded_elements]

        for element in included_elements:

            if isinstance(element, str):
                included2 = False
                for r in returns:
                    for rr in r.value:
                        if rr.__class__.__name__ == element:
                            Logger.info('Found included element: ' + element)
                            included2 = True

                if not included2:
                    Logger.error('Included element not found: ' + element)

        for element in excluded_elements:

            if isinstance(element, str):
                excluded2 = False
                for r in returns:
                    for rr in r.value:
                        if rr.__class__.__name__ == element:
                            Logger.error('Found excluded element: ' + element)
                            excluded = True
                if not excluded2:
                    Logger.info('Excluded element not found: ' + element)


if __name__ == '__main__':
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
