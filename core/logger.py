'''基于logging的日志器。'''
import logging
from abc import ABC, abstractmethod


class AbstractLogger(ABC):
    @abstractmethod
    def info(self, msg):
        pass

    @abstractmethod
    def error(self, msg):
        pass

    @abstractmethod
    def debug(self, msg):
        pass

    @abstractmethod
    def warn(self, msg):
        pass

    @abstractmethod
    def exception(self, msg):
        pass


class Logginglogger(AbstractLogger):
    def __init__(self, fmt="[%(asctime)s][%(levelname)s]: %(msg)s", **kwargs):
        logging.basicConfig(
            format=fmt,
            level=logging.INFO if not kwargs.get("debug") else logging.DEBUG
        )
        self.log = logging.getLogger('akaribot.logger')
        self.log.setLevel(logging.INFO)

    def info(self, msg):
        return self.log.info(msg)

    def error(self, msg):
        return self.log.error(msg)

    def debug(self, msg):
        return self.log.debug(msg)

    def warn(self, msg):
        return self.log.warning(msg)

    def exception(self, msg):
        return self.log.exception(msg)


Logger = Logginglogger()
