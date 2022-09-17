import asyncio
import asyncio.subprocess
import os
import shutil
import subprocess
import sys
from time import sleep

import psutil
from loguru import logger

from config import Config
from database import BotDBUtil, session
from database.tables import DBVersion

encode = 'UTF-8'


class RestartBot(BaseException):
    pass


def get_pid(name):
    return [p.pid for p in psutil.process_iter() if p.name().find(name) != -1]


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


def init_bot():
    cache_path = os.path.abspath(Config('cache_path'))
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        os.mkdir(cache_path)
    else:
        os.mkdir(cache_path)

    base_superuser = Config('base_superuser')
    if base_superuser:
        BotDBUtil.SenderInfo(base_superuser).edit('isSuperUser', True)


pidlst = []


async def run_bot():
    pid_cache = os.path.abspath('.pid_last')
    if os.path.exists(pid_cache):
        with open(pid_cache, 'r') as f:
            pid_last = f.read().split('\n')
            running_pids = get_pid('python')
            for pid in pid_last:
                if int(pid) in running_pids:
                    try:
                        os.kill(int(pid), 9)
                    except (PermissionError, ProcessLookupError):
                        pass
        os.remove(pid_cache)
    envs = os.environ.copy()
    envs['PYTHONIOENCODING'] = 'UTF-8'
    envs['PYTHONPATH'] = os.path.abspath('.')
    botdir = './bots/'
    bots_list = os.listdir(botdir)

    async def get_async(process: asyncio.subprocess.Process):
        line = await process.stderr.readline()
        try:
            logger.info(line.decode(encode)[:-1])
        except UnicodeDecodeError:
            encode_list = ['GBK']
            for e in encode_list:
                try:
                    logger.warning(f'Cannot decode string from UTF-8, decode with {e}: '
                                   + line.decode(e)[:-1])
                    break
                except Exception:
                    if encode_list[-1] != e:
                        logger.warning(f'Cannot decode string from {e}, '
                                       f'attempting with {encode_list[encode_list.index(e) + 1]}.')
                    else:
                        logger.error(f'Cannot decode string from {e}, no more attempts.')

        if process.returncode == 233:
            logger.warning(f'{process.pid} exited with code 233, restart all bots.')
            pidlst.remove(process.pid)
            raise RestartBot

        if process.returncode is not None:
            return

        return await get_async(process)

    tasks = []

    for b in bots_list:
        bot = os.path.abspath(f'{botdir}{b}/bot.py')
        if os.path.exists(bot):
            p = await asyncio.create_subprocess_shell(f'python {bot}', stdout=asyncio.subprocess.PIPE,
                                                      stderr=asyncio.subprocess.PIPE,
                                                      cwd=os.path.abspath('.'), env=envs)
            pidlst.append(p.pid)
            tasks.append(get_async(p))
            tasks.append(p.wait())

    with open(pid_cache, 'w') as c:
        c.write('\n'.join(str(p) for p in pidlst))

    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    init_bot()
    logger.remove()
    logger.add(sys.stderr, format='{message}', level="INFO")
    query_dbver = session.query(DBVersion).first()
    if query_dbver is None:
        session.add_all([DBVersion(value='2')])
        session.commit()
        query_dbver = session.query(DBVersion).first()
    if (current_ver := int(query_dbver.value)) < (target_ver := BotDBUtil.database_version):
        logger.info(f'Updating database from {current_ver} to {target_ver}...')
        from database.update import update_database

        update_database()
        logger.info('Database updated successfully!')
    try:
        while True:
            try:
                asyncio.run(run_bot())  # Process will block here so
                logger.error('All bots exited unexpectedly, please check the output')
                break
            except RestartBot:
                for x in pidlst:
                    try:
                        os.kill(x, 9)
                    except (PermissionError, ProcessLookupError):
                        pass
                pidlst.clear()
                sleep(5)
                continue
    except KeyboardInterrupt:
        for x in pidlst:
            try:
                os.kill(x, 9)
            except (PermissionError, ProcessLookupError):
                pass
