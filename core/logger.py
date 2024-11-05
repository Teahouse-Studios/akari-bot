"""基于loguru的日志器。"""
import os
import re
import sys

from loguru import logger

from core.config import Config
from core.path import logs_path


debug = Config('debug', False)

if not os.path.exists(logs_path):
    os.mkdir(logs_path)

bot_name = re.split(r'[/\\]', sys.path[0])[-1].title()

args = sys.argv
if 'subprocess' in args:
    bot_name = args[-1].title()
if args[0].lower() == 'console.py':
    bot_name = 'Console'

basic_logger_format = (
    f"<cyan>[{bot_name}]</cyan>"
    "<yellow>[{name}:{function}:{line}]</yellow>"
    "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
    "<level>[{level}]:{message}</level>"
)


class LoggingLogger:
    def __init__(self):
        self.log = logger
        self.log.remove()
        self.log.add(
            sys.stderr,
            format=basic_logger_format,
            level="DEBUG" if debug else "INFO",
            colorize=True
        )

        log_file_path = os.path.join(logs_path, f"{bot_name}_{{time:YYYY-MM-DD}}.log")
        self.log.add(
            log_file_path,
            format=basic_logger_format,
            retention="10 days",
            encoding="utf8"
        )

        self.info = self.log.info
        self.error = self.log.error
        self.debug = self.log.debug
        self.warning = self.log.warning
        self.exception = self.log.exception

        if debug:
            self.log.warning("Debug mode is enabled.")


Logger = LoggingLogger()
