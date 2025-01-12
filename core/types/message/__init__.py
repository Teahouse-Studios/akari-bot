from __future__ import annotations

from typing import Any, Optional, Union

from attrs import define


@define
class MsgInfo:
    target_id: str
    sender_id: str
    sender_prefix: str
    target_from: str
    sender_from: str
    client_name: str
    message_id: Union[int, str]
    reply_id: Optional[Union[int, str]] = None


@define
class Session:
    """
    一个便于调用框架内部方法的插槽，根据不同的框架可能会有不同的实现。（由于没有类型提示，除非功能实现必须，不建议依赖它进行实现）
    """

    message: Any
    target: Any
    sender: Any


@define
class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    args: dict


__all__ = ["MsgInfo", "Session", "ModuleHookContext"]
