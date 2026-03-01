"""
内置工具模块 - 提供命令前缀和确认词等系统级配置。

该模块从配置文件中加载命令前缀和确认词的配置项，
并对其进行去重和处理，供系统其他部分使用。
"""

from core.config import Config
from core.constants.default import (
    confirm_command_default,
    command_prefix_default,
)
from core.utils.func import unique_list


# 确认命令列表 - 用户确认操作时可使用的关键词，加上默认的圆形符号表情
# 从配置中加载，去重处理，并默认添加 ⭕ 符号作为万能确认符
confirm_command = unique_list(
    filter(str.strip, Config("confirm_command", confirm_command_default)) or confirm_command_default
) + ["⭕"]  # 确认词

# 命令前缀列表 - 触发命令的前缀符号，如 "/" 或 "~"
# 从配置中加载，进行去重处理
command_prefix = unique_list(
    filter(str.strip, Config("command_prefix", command_prefix_default)) or command_prefix_default
)  # 命令前缀

__all__ = ["confirm_command", "command_prefix"]
