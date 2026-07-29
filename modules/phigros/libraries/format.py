import ast

from core.builtins.message.internal import I18NContext
from core.logger import Logger

# gameKey 的 type 为 Bits[5]，五位依次对应下列类别。
KEY_CATEGORIES = ("collection_read", "single", "collection", "background", "avatar")

# money 为五个 VarInt，按单位升序排列。
DATA_UNITS = ("KB", "MB", "GB", "TB", "PB")

DIFF_NAMES = ("EZ", "HD", "IN", "AT")


def decode_challenge(challenge: int) -> tuple[int, int]:
    """拆分课题分为段位与分数。

    :param challenge: 存档中的课题分原始值。
    :return: 段位与分数。
    """
    return challenge // 100, challenge % 100


def count_game_keys(key_list: dict) -> dict[str, int]:
    """按 type 位统计各类解锁数量。

    :param key_list: gameKey 的 keyList 字段。
    """
    counts = dict.fromkeys(KEY_CATEGORIES, 0)
    for name, key in key_list.items():
        try:
            bits = ast.literal_eval(key.get("type", ""))
        except (ValueError, SyntaxError):
            Logger.warning(f"Malformed game key type for {name}: {key.get('type')}")
            continue
        if not isinstance(bits, list):
            Logger.warning(f"Unexpected game key type for {name}: {bits}")
            continue
        for index, category in enumerate(KEY_CATEGORIES):
            if index < len(bits) and bits[index]:
                counts[category] += 1
    return counts


def format_data(money: list[int]) -> str:
    """把 Data 值拼为带单位的文本。

    :param money: gameProgress 的 money 字段，五个数按单位升序排列。
    """
    parts = [f"{value} {unit}" for value, unit in zip(money, DATA_UNITS) if value]
    return " ".join(reversed(parts)) if parts else f"0 {DATA_UNITS[0]}"


def _yes_no(value) -> str:
    """把布尔状态转为供 i18n 模板插值的标记。

    :param value: 存档中的原始值，通常为 0 或 1。
    """
    return "✓" if value else "✗"


def summary_lines(summary: dict, progress: dict | None) -> list:
    """组装玩家概览。

    :param summary: getSummary() 的返回值。
    :param progress: gameProgress 解析结果，为 None 时省略 Data 值。
    """
    rank, score = decode_challenge(int(summary.get("challenge", 0)))
    lines = [
        I18NContext("phigros.message.info.rks", rks=f"{summary.get('rks', 0):.4f}"),
        I18NContext("phigros.message.info.challenge", rank=rank, score=score),
        I18NContext("phigros.message.info.game_version", version=summary.get("gameVersion", 0)),
        I18NContext("phigros.message.info.save_version", version=summary.get("saveVersion", 0)),
        I18NContext("phigros.message.info.updated_at", time=summary.get("updateAt", "")),
    ]
    for name in DIFF_NAMES:
        stat = summary.get(name) or [0, 0, 0]
        lines.append(
            I18NContext(
                "phigros.message.info.difficulty_stat",
                difficulty=name,
                cleared=stat[0],
                full_combo=stat[1],
                phi=stat[2],
            )
        )
    if progress:
        lines.append(I18NContext("phigros.message.info.data", data=format_data(progress.get("money", []))))
    return lines


def unlock_lines(progress: dict, game_key: dict) -> list:
    """组装解锁进度。

    :param progress: gameProgress 解析结果。
    :param game_key: gameKey 解析结果。
    """
    counts = count_game_keys(game_key.get("keyList", {}))
    lines = [
        I18NContext("phigros.message.unlock.single", count=counts["single"]),
        I18NContext("phigros.message.unlock.collection", count=counts["collection"]),
        I18NContext("phigros.message.unlock.collection_read", count=counts["collection_read"]),
        I18NContext("phigros.message.unlock.background", count=counts["background"]),
        I18NContext("phigros.message.unlock.avatar", count=counts["avatar"]),
    ]
    lines.append(
        I18NContext(
            "phigros.message.unlock.chapter8",
            begin=_yes_no(progress.get("chapter8UnlockBegin")),
            second=_yes_no(progress.get("chapter8UnlockSecondPhase")),
            passed=_yes_no(progress.get("chapter8Passed")),
        )
    )
    return lines


def settings_lines(settings: dict) -> list:
    """组装游戏设置。

    :param settings: settings 解析结果。
    """
    return [
        I18NContext("phigros.message.settings.device", name=settings.get("deviceName", "")),
        I18NContext("phigros.message.settings.bright", value=f"{settings.get('bright', 0):.2f}"),
        I18NContext("phigros.message.settings.music_volume", value=f"{settings.get('musicVolume', 0):.2f}"),
        I18NContext("phigros.message.settings.effect_volume", value=f"{settings.get('effectVolume', 0):.2f}"),
        I18NContext("phigros.message.settings.hitsound_volume", value=f"{settings.get('hitSoundVolume', 0):.2f}"),
        I18NContext("phigros.message.settings.offset", value=f"{settings.get('soundOffset', 0):.3f}"),
        I18NContext("phigros.message.settings.note_scale", value=f"{settings.get('noteScale', 0):.2f}"),
        I18NContext("phigros.message.settings.chord_support", value=_yes_no(settings.get("chordSupport"))),
        I18NContext("phigros.message.settings.fcap_indicator", value=_yes_no(settings.get("fcAPIndicator"))),
        I18NContext("phigros.message.settings.hit_sound", value=_yes_no(settings.get("enableHitSound"))),
        I18NContext("phigros.message.settings.low_resolution", value=_yes_no(settings.get("lowResolutionMode"))),
    ]
