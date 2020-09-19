import time

import psutil


async def main():
    Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    time.sleep(0.5)
    Cpu_usage = psutil.cpu_percent()
    RAM = int(psutil.virtual_memory().total / (1027 * 1024))
    RAM_percent = psutil.virtual_memory().percent
    Swap = int(psutil.swap_memory().total / (1027 * 1024))
    Swap_percent = psutil.swap_memory().percent
    BFH = r'%'
    return ("Pong!\n" + "系统运行时间：%s" % Boot_Start \
            + "\n当前CPU使用率：%s%s" % (Cpu_usage, BFH) \
            + "\n物理内存：%dM 使用率：%s%s" % (RAM, RAM_percent, BFH) \
            + "\nSwap内存：%dM 使用率：%s%s" % (Swap, Swap_percent, BFH))


command = {'ping': 'ping'}
