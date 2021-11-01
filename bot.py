import datetime
import logging
import os
import subprocess
import traceback
from queue import Queue, Empty
from threading import Thread
from time import sleep

from init import init_bot

encode = 'UTF-8'


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


init_bot()

logging.basicConfig(format="%(msg)s", level=logging.INFO)
botdir = './core/bots/'
lst = os.listdir(botdir)
runlst = []
for x in lst:
    bot = os.path.abspath(f'{botdir}{x}/bot.py')
    if os.path.exists(bot):
        p = subprocess.Popen(f'python {bot}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             cwd=os.path.abspath('.'))
        runlst.append(p)
q = Queue()
threads = []
for p in runlst:
    threads.append(Thread(target=enqueue_output, args=(p.stdout, q)))

for t in threads:
    t.daemon = True
    t.start()

start = datetime.datetime.now()

while True:
    try:
        line = q.get_nowait()
    except Empty:
        pass
    except KeyboardInterrupt:
        for x in runlst:
            x.kill()
    else:
        try:
            logging.info(line[:-1].decode(encode))
        except Exception:
            print(line)
            traceback.print_exc()

    # break when all processes are done.
    if all(p.poll() is not None for p in runlst):
        break

    sleep(0.001)
