import sys

from loguru import logger

try:
    logger.remove(0)
except ValueError:
    pass

Logger = logger.bind(name="unittest")

logger_format = (
    "<cyan>[unittest]</cyan>"
    "<yellow>[{name}:{function}:{line}]</yellow>"
    "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
    "<level>[{level}]:{message}</level>"
)
Logger.add(
    sys.stdout,
    format=logger_format,
    level="INFO",
    colorize=True
)
