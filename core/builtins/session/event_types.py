from typing import Literal, TypeAlias


EventName: TypeAlias = (
    Literal[
        "member_joined",
        "member_left",
        "guild_member_joined",
        "guild_member_left",
    ]
    | str
)
"""内置事件名提示；保留 str 以兼容模块和适配器定义的自定义事件。"""


__all__ = ["EventName"]
