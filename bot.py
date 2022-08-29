import os
import shutil
import subprocess
import sys
from queue import Queue, Empty
from threading import Thread
from time import sleep

import psutil
from loguru import logger

from config import Config
from database import BotDBUtil, session, DBVersion

encode = 'UTF-8'


class RestartBot(Exception):
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


def run_bot():
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
    lst = os.listdir(botdir)
    runlst = []
    for x in lst:
        bot = os.path.abspath(f'{botdir}{x}/bot.py')
        if os.path.exists(bot):
            p = subprocess.Popen(['python', bot], shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 cwd=os.path.abspath('.'), env=envs)
            runlst.append(p)
            pidlst.append(p.pid)

    with open(pid_cache, 'w') as c:
        c.write('\n'.join(str(p) for p in pidlst))

    q = Queue()
    threads = []
    for p in runlst:
        threads.append(Thread(target=enqueue_output, args=(p.stdout, q)))

    for t in threads:
        t.daemon = True
        t.start()

    while True:
        try:
            line = q.get_nowait()
        except Empty:
            pass
        else:
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

        # break when all processes are done.
        if all(p.poll() is not None for p in runlst):
            break

        for p in runlst:
            if p.poll() == 233:
                logger.warning(f'{p.pid} exited with code 233, restart all bots.')
                pidlst.remove(p.pid)
                raise RestartBot
        sleep(0.001)


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
                run_bot()  # Process will block here so
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
