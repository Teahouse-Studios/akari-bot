from core.config import Config
from core.constants import (
    PrivateAssets,
    Secret,
    confirm_command_default,
    command_prefix_default,
)
from core.utils.info import get_all_target_prefix, get_all_sender_prefix

confirm_command = list(
    filter(str.strip, Config("confirm_command", confirm_command_default))
    or confirm_command_default
)  # 确认指令
command_prefix = list(
    filter(str.strip, Config("command_prefix", command_prefix_default))
    or command_prefix_default
)  # 消息前缀


def determine_target_from(target_id: str):
    """
    确定目标 ID 的前缀。
    :param target_id: 目标 ID
    :return: 前缀
    """
    for prefix in get_all_target_prefix():
        if target_id.startswith(prefix):
            return prefix
    return None


def determine_sender_from(sender_id: str):
    """
    确定发送者 ID 的前缀。
    :param sender_id: 发送者 ID
    :return: 前缀
    """
    for prefix in get_all_sender_prefix():
        if sender_id.startswith(prefix):
            return prefix
    return None


__all__ = ["confirm_command", "command_prefix", "PrivateAssets", "Secret"]
