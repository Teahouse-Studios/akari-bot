from __future__ import annotations

import asyncio
from typing import List, Union, Dict, Coroutine, Awaitable, Any

from core.constants.exceptions import FinishedException
from .chain import MessageChain
from .internal import Plain, Image, Voice, Embed, Url, ErrorMessage


class MsgInfo:
    __slots__ = ["target_id", "sender_id", "sender_prefix", "target_from", "sender_info", "sender_from", "client_name",
                 "message_id", "reply_id"]

    def __init__(self,
                 target_id: Union[int, str],
                 sender_id: Union[int, str],
                 sender_prefix: str,
                 target_from: str,
                 sender_from: str,
                 client_name: str,
                 message_id: Union[int, str],
                 reply_id: Union[int, str] = None):
        self.target_id = target_id
        self.sender_id = sender_id
        self.sender_prefix = sender_prefix
        self.target_from = target_from
        self.sender_from = sender_from
        self.client_name = client_name
        self.message_id = message_id
        self.reply_id = reply_id

    def __repr__(self):
        return f'MsgInfo(target_id={self.target_id}, sender_id={self.sender_id}, sender_prefix={self.sender_prefix},' \
            f' target_from={self.target_from}, sender_from={self.sender_from}, client_name={self.client_name}, ' \
            f'message_id={self.message_id}, reply_id={self.reply_id})'


class Session:
    def __init__(self, message, target, sender):
        self.message = message
        self.target = target
        self.sender = sender

    def __repr__(self):
        return f'Session(message={self.message}, target={self.target}, sender={self.sender})'


class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    def __init__(self, args: dict):
        self.args = args


__all__ = ["MsgInfo", "Session",
           "ModuleHookContext", "MessageChain"]
