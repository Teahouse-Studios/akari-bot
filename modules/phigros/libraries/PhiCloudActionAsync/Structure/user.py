# ----------------------- 导入 -----------------------
from .DataType import Byte, String

# ---------------------- 定义 ----------------------


class user01:
    file_head = b"\x01"

    showPlayerId: Byte
    """右上角展示用户 id"""

    selfIntro: String
    """自我介绍"""

    avatar: String
    """头像"""

    background: String
    """背景曲绘"""
