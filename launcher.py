import sys
import os
import importlib

from core.logger import Logger
from core.utils.info import Info

arg = sys.argv
bots_listdir = os.listdir('./bots/')

if arg[-1] in bots_listdir:
    Logger.info(f"[{arg[-1]}] Here we go!")
    if 'subprocess' in sys.argv:
        Info.subprocess = True
    dir_path = os.path.join(os.path.abspath('.'), f"bots/{arg[-1]}")
    if os.path.isdir(dir_path) and (os.path.exists(f"{dir_path}/bot.py")):
        importlib.import_module(f"bots.{arg[-1]}.bot")
    else:
        Logger.error(f"[{arg[-1]}] ???, bot.py not found, abort.")
else:
    Logger.error("[Launcher] No bot specified, abort.")
