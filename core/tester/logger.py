import os
import sys
import traceback
from pathlib import Path

from loguru import logger

from core.config.core import CoreConfig

test_log_path = Path("test_result.log")

if os.path.exists(test_log_path):
    try:
        os.unlink(test_log_path)
    except OSError:
        # 并发运行的测试进程可能已占用该文件；此时沿用其内容继续追加。
        pass


class TestLoggingLogger:
    def __init__(self, name: str):
        self.log = logger.bind(name=name)

        def record_filter(record):
            return record["extra"].get("name") == name

        self.log.add(
            sys.stdout,
            format="<level>{message}</level>",
            level="TRACE" if CoreConfig.debug else "INFO",
            colorize=True,
            filter=record_filter,
        )
        self.log.add(
            sink=test_log_path,
            format="<level>{message}</level>",
            level="INFO",
            filter=record_filter,
            encoding="utf8",
        )

        self.trace = self.log.trace
        self.debug = self.log.debug
        self.info = self.log.info
        self.success = self.log.success
        self.warning = self.log.warning
        self.error = self.log.error
        self.critical = self.log.critical

    def exception(self, message: str | None = None):
        if message:
            self.error(f"{message}\n{traceback.format_exc()}")
        else:
            self.error(traceback.format_exc())
