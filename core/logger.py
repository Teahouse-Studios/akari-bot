from abc import ABC, abstractmethod
import logging


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


class Logger(AbstractLogger):
    def __init__(self, **kwargs) -> None:
        logging.basicConfig(
            format="[%(asctime)s][%(levelname)s]: %(message)s",
            level=logging.INFO if not kwargs.get("debug") else logging.DEBUG,
        )

    @classmethod
    def info(cls, msg):
        return logging.info(msg)

    @classmethod
    def error(cls, msg):
        return logging.error(msg)

    @classmethod
    def debug(cls, msg):
        return logging.debug(msg)

    @classmethod
    def warn(cls, msg):
        return logging.warning(msg)

    @classmethod
    def exception(cls, msg):
        return logging.exception(msg)
