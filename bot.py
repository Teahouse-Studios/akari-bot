import logging
import subprocess
import traceback
from queue import Queue, Empty
from threading import Thread
from time import sleep

import psutil

import os
import shutil

from config import Config
from database import BotDBUtil

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
    cache_path = os.path.abspath('./cache/')
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
            print(running_pids)
            print(pid_last)
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
    botdir = './core/bots/'
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
                logging.info(line[:-1].decode(encode))
            except Exception:
                print(line)
                logging.error(traceback.format_exc())

        # break when all processes are done.
        if all(p.poll() is not None for p in runlst):
            break

        for p in runlst:
            if p.poll() == 233:
                logging.warning(f'{p.pid} exited with code 233, restart all bots.')
                pidlst.remove(p.pid)
                raise RestartBot
        sleep(0.001)


if __name__ == '__main__':
    init_bot()
    logging.basicConfig(format="%(msg)s", level=logging.INFO)
    try:
        while True:
            try:
                run_bot()
                logging.fatal('All bots exited unexpectedly, please check the output')
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
