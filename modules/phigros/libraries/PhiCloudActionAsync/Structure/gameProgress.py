# ----------------------- 导入 -----------------------
from .DataType import Bit, String, VarInt, ShortInt, Money, Bits

# ---------------------- 定义 ----------------------


class gameProgress04:
    """
    版本号 ≥ 3.8.1

    新增了 "flagOfSongRecordKeyTakumi"
    """

    file_head = b"\x04"

    isFirstRun: Bit
    """是否首次运行"""

    legacyChapterFinished: Bit
    """过去的章节是否完成"""

    alreadyShowCollectionTip: Bit
    """是否展示收藏品 Tip"""

    alreadyShowAutoUnlockINTip: Bit
    """是否展示自动解锁 IN Tip"""

    completed: String
    """剧情完成 (用于显示全部歌曲和课题模式入口)"""

    songUpdateInfo: VarInt

    challengeModeRank: ShortInt
    """课题分"""

    money: Money
    """Data 值"""

    unlockFlagOfSpasmodic: Bits[4]
    """Spasmodic 解锁"""

    unlockFlagOfIgallta: Bits[4]
    """Igallta 解锁"""

    unlockFlagOfRrharil: Bits[4]
    """Rrhar'il 解锁"""

    flagOfSongRecordKey: Bits
    """
    部分歌曲 IN 达到 S 解锁 AT

    (倒霉蛋, 船, Shadow, 心之所向, inferior, DESTRUCTION 3,2,1, Distorted Fate, Cuvism)
    """

    randomVersionUnlocked: Bits[6]
    """Random 切片解锁"""

    chapter8UnlockBegin: Bit
    """第八章入场"""

    chapter8UnlockSecondPhase: Bit
    """第八章第二阶段"""

    chapter8Passed: Bit
    """第八章通过"""

    chapter8SongUnlocked: Bits[6]
    """第八章各曲目解锁"""

    flagOfSongRecordKeyTakumi: Bits[3]
    """第四章 Takumi AT 解锁"""


class gameProgress03:
    """版本号 < 3.8.1"""

    file_head = b"\x03"

    isFirstRun: Bit
    """是否首次运行"""

    legacyChapterFinished: Bit
    """过去的章节是否完成"""

    alreadyShowCollectionTip: Bit
    """是否展示收藏品 Tip"""

    alreadyShowAutoUnlockINTip: Bit
    """是否展示自动解锁 IN Tip"""

    completed: String
    """剧情完成 (用于显示全部歌曲和课题模式入口)"""

    songUpdateInfo: VarInt

    challengeModeRank: ShortInt
    """课题分"""

    money: Money
    """Data 值"""

    unlockFlagOfSpasmodic: Bits[4]
    """Spasmodic 解锁"""

    unlockFlagOfIgallta: Bits[4]
    """Igallta 解锁"""

    unlockFlagOfRrharil: Bits[4]
    """Rrhar'il 解锁"""

    flagOfSongRecordKey: Bits
    """
    部分歌曲 IN 达到 S 解锁 AT

    (倒霉蛋, 船, Shadow, 心之所向, inferior, DESTRUCTION 3,2,1, Distorted Fate, Cuvism)
    """

    randomVersionUnlocked: Bits[6]
    """Random 切片解锁"""

    chapter8UnlockBegin: Bit
    """第八章入场"""

    chapter8UnlockSecondPhase: Bit
    """第八章第二阶段"""

    chapter8Passed: Bit
    """第八章通过"""

    chapter8SongUnlocked: Bits[6]
    """第八章各曲目解锁"""
