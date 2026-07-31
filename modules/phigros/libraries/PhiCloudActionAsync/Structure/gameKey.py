# ----------------------- 导入 -----------------------
from .DataType import GameKey, Bits, Byte

# ---------------------- 定义 ----------------------


class gameKey03:
    """
    版本号 ≥ 3.9.0

    新增 "sideStory4BeginReadKey" 和 "oldScoreClearedV390"
    """

    file_head = b"\x03"

    keyList: GameKey
    """
    游戏中所有 Key 的状态值

    结构:
        type: key 的状态标志 (收藏品阅读、单曲解锁、收藏品、背景、头像)
        flag: key 的标记 (长度与 type 中 1 的数量一致，每位值相同，与收藏品碎片收集有关，默认为 1)
    """

    lanotaReadKeys: Bits[6]
    """Lanota 收藏品阅读进度 (解锁倒霉蛋和船的 AT)"""

    camelliaReadKey: Bits
    """极星卫收藏品阅读进度 (解锁 S.A.T.E.L.L.I.T.E. 的 AT)"""

    sideStory4BeginReadKey: Byte
    """解锁支线 4"""

    oldScoreClearedV390: Byte
    """是否已清除改谱之前的成绩 (如果为 0 则会清除)"""


class gameKey02:
    """版本号 < 3.9.0"""

    file_head = b"\x02"

    keyList: GameKey

    lanotaReadKeys: Bits[6]
    """Lanota 收藏品阅读进度 (解锁倒霉蛋和船的 AT)"""

    camelliaReadKey: Bits
    """极星卫收藏品阅读进度 (解锁 S.A.T.E.L.L.I.T.E. 的 AT)"""
