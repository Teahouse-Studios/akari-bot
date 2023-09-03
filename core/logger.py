'''基于logging的日志器。'''
import os
import re
import sys

from loguru import logger

from config import Config

debug = Config('debug')

logpath = os.path.abspath('./logs')
if not os.path.exists(logpath):
    os.mkdir(logpath)

bot_name = re.split(r'[/\\]', sys.path[0])[-1].title()
basic_logger_format = "<cyan>[" + bot_name + \
                      "]</cyan><yellow>[{name}:{function}:{line}]</yellow><green>[{time:YYYY-MM-DD HH:mm:ss}]</green><level>[{level}]:{message}</level>"


class Logginglogger:
    def __init__(self):
        self.log = logger
        self.log.remove()
        self.log.add(sys.stderr, format=basic_logger_format, level="DEBUG" if debug else "INFO", colorize=True)
        self.log.add(logpath + '/' + bot_name + "_{time:YYYY-MM-DD}.log", format=basic_logger_format,
                     retention="10 days", encoding="utf8")
        self.info = self.log.info
        self.error = self.log.error
        self.debug = self.log.debug
        self.warn = self.log.warning
        self.exception = self.log.exception
        if debug:
            self.log.warning("Debug mode is enabled.")


Logger = Logginglogger()
