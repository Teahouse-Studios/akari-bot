import sys
import importlib

from core.logger import Logger
from core.utils.info import Info

arg = sys.argv
if not sys.argv[0].endswith('.py'):
    Info.build_mode = True

Logger.info(f"[{arg[-1]}] Here we go!")
if 'subprocess' in sys.argv:
    Info.subprocess = True
try:
    importlib.import_module(f"bots.{arg[-1]}.bot")
except ModuleNotFoundError:
    Logger.error(f"[{arg[-1]}] ???, entry not found.")
    sys.exit(1)
