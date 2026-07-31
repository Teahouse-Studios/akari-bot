"""日志转发。

上游实现会创建 ./log/ 目录、接管 sys.excepthook 并依赖 colorlog，三者均与本项目冲突，
故整体替换为对项目日志器的转发。对外仍以 logger 之名暴露，包内导入方无需改动。
"""

from core.logger import Logger

logger = Logger
