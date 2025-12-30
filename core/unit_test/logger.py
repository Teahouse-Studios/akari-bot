import sys

from loguru import logger

try:
    logger.remove(0)
except ValueError:
    pass

Logger = logger.bind(name="uniTest")

logger_format = (
    "<cyan>[uniTest]</cyan>"
    "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
    "<level>[{level}]:{message}</level>"
)
Logger.add(
    sys.stdout,
    format=logger_format,
    level="INFO",
    colorize=True
)
