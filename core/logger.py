"""机器人内置的基于`loguru`的日志工具。"""

import os
import re
import sys
import traceback
from typing import Optional

from loguru import logger

from core.config import Config
from core.constants.path import logs_path

os.makedirs(logs_path, exist_ok=True)

bot_name = re.split(r"[/\\]", sys.path[0])[-1]

args = sys.argv
if "subprocess" in args:
    bot_name = args[-1]


def basic_logger_format(bot_name: str):
    return (
        f"<cyan>[{bot_name.upper()}]</cyan>"
        "<yellow>[{name}:{function}:{line}]</yellow>"
        "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green>"
        "<level>[{level}]:{message}</level>"
    )


class LoggingLogger:
    def __init__(self, name):

        self.log = logger
        self.trace = logger.trace
        """跟踪信息，用于细粒度调试。启用debug配置项后在控制台显示，不会被记录到日志中。不建议在正式环境中使用。"""
        self.debug = logger.debug
        """调试信息，记录程序执行的细节和状态变化。启用debug配置项后在控制台显示。"""
        self.info = logger.info
        """常规信息，记录程序的正常运行状态。"""
        self.success = logger.success
        """成功信息，记录任务完成的情况。"""
        self.warning = logger.warning
        """警告信息，记录产生潜在风险但不影响程序运作的情况。"""
        self.error = logger.error
        """错误信息，记录产生错误或异常等须及时处理的情况。"""
        self.critical = logger.critical
        """严重错误信息，记录产生可能使程序崩溃的情况。"""

    def rename(self, name):
        try:
            logger.remove(0)
        except ValueError:
            # 如果没有默认的日志处理器，则忽略此错误
            pass
        self.log = logger.bind(name=name)
        self.log.add(
            sys.stderr,
            format=basic_logger_format(name),
            level="TRACE" if Config("debug", False) else "INFO",
            colorize=True,
            filter=lambda record: record["extra"].get("name") == name
        )

        self.log.add(
            sink=os.path.join(logs_path, f"{name}_debug_{{time:YYYY-MM-DD}}.log"),
            format=basic_logger_format(name),
            rotation="00:00",
            retention="1 day",
            level="DEBUG",
            filter=lambda record: record["level"].name == "DEBUG" and record["extra"].get("name") == name,
            encoding="utf8",
        )
        self.log.add(
            sink=os.path.join(logs_path, f"{name}_{{time:YYYY-MM-DD}}.log"),
            format=basic_logger_format(name),
            rotation="00:00",
            retention="10 days",
            level="INFO",
            encoding="utf8",
            filter=lambda record: record["extra"].get("name") == name
        )
        self.trace = self.log.trace
        self.debug = self.log.debug
        self.info = self.log.info
        self.success = self.log.success
        self.warning = self.log.warning
        self.error = self.log.error
        self.critical = self.log.critical

    def exception(self, message: Optional[str] = None):
        """自带 traceback 的错误日志，用于记录与跟踪异常信息。"""
        if message:
            self.error(f"{message}\n{traceback.format_exc()}")
        else:
            self.error(traceback.format_exc())


Logger = LoggingLogger(bot_name)
