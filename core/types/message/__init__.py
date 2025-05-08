from __future__ import annotations

from attrs import define


@define
class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    args: dict


__all__ = ["ModuleHookContext"]
