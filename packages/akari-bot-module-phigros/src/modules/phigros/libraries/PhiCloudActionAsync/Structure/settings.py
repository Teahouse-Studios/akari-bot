# ----------------------- 导入 -----------------------
from .DataType import Bit, String, Float

# ---------------------- 定义 ----------------------


class settings01:
    file_head = b"\x01"

    chordSupport: Bit
    """多押辅助"""

    fcAPIndicator: Bit
    """FC/AP 指示器"""

    enableHitSound: Bit
    """打击音效"""

    lowResolutionMode: Bit
    """低分辨率模式"""

    deviceName: String
    """设备名"""

    bright: Float
    """背景亮度"""

    musicVolume: Float
    """音乐音量"""

    effectVolume: Float
    """界面音效音量"""

    hitSoundVolume: Float
    """打击音效音量"""

    soundOffset: Float
    """谱面延迟"""

    noteScale: Float
    """按键缩放"""
