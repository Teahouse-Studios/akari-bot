from .DataType import Byte, ShortInt, Float, VarInt, String, Summary


class summary:
    saveVersion: Byte
    """存档版本号"""

    challenge: ShortInt
    """课题分"""

    rks: Float
    """RKS"""

    gameVersion: VarInt
    """游戏版本号"""

    avatar: String
    """头像"""

    EZ: Summary
    """EZ 难度谱面的完成情况（Cleared, Full Combo, Phi）"""

    HD: Summary
    """HD 难度谱面的完成情况（Cleared, Full Combo, Phi）"""

    IN: Summary
    """IN 难度谱面的完成情况（Cleared, Full Combo, Phi）"""

    AT: Summary
    """AT 难度谱面的完成情况（Cleared, Full Combo, Phi）"""
