import sys
import importlib

from core.logger import Logger
from core.utils.info import Info

arg = sys.argv
if not sys.argv[0].endswith('.py'):
    Info.binary_mode = True

if len(arg) > 1:
    Logger.info(f"[{arg[-1]}] Here we go!")
    if 'subprocess' in sys.argv:
        Info.subprocess = True
    try:
        importlib.import_module(f"bots.{arg[-1]}.bot")
    except ModuleNotFoundError:
        Logger.error(f"[{arg[-1]}] ???, entry not found.")
        sys.exit(1)
else:
    Logger.error("Please specify the entry.")
    sys.exit(1)
