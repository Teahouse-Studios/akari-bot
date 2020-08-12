import psutil
import time


async def ping():
    Boot_Start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    time.sleep(0.5)
    Cpu_usage = psutil.cpu_percent()
    RAM = int(psutil.virtual_memory().total / (1027 * 1024))
    RAM_percent = psutil.virtual_memory().percent
    Swap = int(psutil.swap_memory().total / (1027 * 1024))
    Swap_percent = psutil.swap_memory().percent
    Net_sent = psutil.net_io_counters().bytes_sent
    Net_recv = psutil.net_io_counters().bytes_recv
    Net_spkg = psutil.net_io_counters().packets_sent
    Net_rpkg = psutil.net_io_counters().packets_recv
    BFH = r'%'
    return ("Pong!\n" + "系统运行时间：%s" % Boot_Start \
            + "\n当前CPU使用率：%s%s" % (Cpu_usage, BFH) \
            + "\n物理内存：%dM 使用率：%s%s" % (RAM, RAM_percent, BFH) \
            + "\nSwap内存：%dM 使用率：%s%s" % (Swap, Swap_percent, BFH))
