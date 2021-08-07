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
            level=logging.INFO if not kwargs.get("debug") else logging.DEBUG,
        )

    def info(self, msg):
        return logging.info(msg)

    def error(self, msg):
        return logging.error(msg)

    def debug(self, msg):
        return logging.debug(msg)

    def warn(self, msg):
        return logging.warning(msg)

    def exception(self, msg):
        return logging.exception(msg)


Logger = Logginglogger()
