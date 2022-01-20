'''基于logging的日志器。'''
import logging
import re
import sys


factory = logging.getLogRecordFactory()
basic_logger_format = "[%(asctime)s][%(botname)s][%(levelname)s][%(pathname)s:%(lineno)d]: %(msg)s"


def record_factory(*args, **kwargs):
    record = factory(*args, **kwargs)
    for x in sys.path:
        record.pathname = record.pathname.replace(x, '')
    record.pathname = record.pathname.replace('\\', '.').replace('/', '.')[1:]
    record.botname = re.split(r'[/\\]', sys.path[0])[-1]
    return record


logging.setLogRecordFactory(record_factory)


class Logginglogger:
    def __init__(self, fmt=basic_logger_format, **kwargs):
        logging.basicConfig(
            format=fmt,
            level=logging.INFO if not kwargs.get("debug") else logging.DEBUG
        )
        self.log = logging.getLogger('akaribot.logger')
        self.log.setLevel(logging.INFO)

        self.info = self.log.info
        self.error = self.log.error
        self.debug = self.log.debug
        self.warn = self.log.warning
        self.exception = self.log.exception


Logger = Logginglogger()
