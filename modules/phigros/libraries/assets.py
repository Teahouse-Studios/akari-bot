import re
import shutil
import string
from pathlib import Path

import orjson

from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download

pgr_assets_path = Path(__file__).parent.parent / "assets"
song_info_path = pgr_assets_path / "song_info.json"
illustration_dir = pgr_assets_path / "illustration"
version_path = pgr_assets_path / "resource_version.txt"

RESOURCE_BASE = "https://raw.githubusercontent.com/7aGiven/Phigros_Resource"
INFO_TSV_URL = f"{RESOURCE_BASE}/refs/heads/info/info.tsv"
DIFF_TSV_URL = f"{RESOURCE_BASE}/refs/heads/info/difficulty.tsv"
VERSION_URL = f"{RESOURCE_BASE}/refs/heads/info/version.txt"
ILLUSTRATION_URL = f"{RESOURCE_BASE}/illustrationLowRes/{{song_id}}.png"

DIFF_NAMES = ("EZ", "HD", "IN", "AT")

_PUNCTUATIONS = (
    "！？｡＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～、。〃〈〉《》「」『』"
    "【】〒〔〕〖〗〘〙〚〛〜・♫☆×♪↑↓²³ "
)


def remove_punctuations(text: str) -> str:
    """去除字符串中的标点与空白并转为小写。

    仅用于用户输入的曲名匹配。曲目 id 与 7aGiven 的键天然一致，不需归一化。

    :param text: 待处理的字符串。
    """
    text = "".join(char for char in text if char not in string.punctuation and char not in _PUNCTUATIONS)
    return re.sub(" +", " ", text).strip().lower()


def _rows(text: str) -> list[list[str]]:
    """按制表符切分 TSV 文本。

    不使用 csv 模块：曲名中可能含有引号，会被 csv 的引用规则误解。

    :param text: TSV 文本。
    """
    return [line.split("\t") for line in text.splitlines() if line.strip()]


def parse_info_tsv(text: str) -> dict[str, dict]:
    """解析 info.tsv。

    每行为曲目 id、曲名、曲师、画师，其后为各难度谱师，列数在 4 至 7 之间浮动。

    :param text: info.tsv 的文本内容。
    """
    result = {}
    for row in _rows(text):
        if len(row) < 4:
            continue
        charter = {name: row[4 + index] for index, name in enumerate(DIFF_NAMES) if 4 + index < len(row)}
        result[row[0]] = {
            "name": row[1],
            "artist": row[2],
            "illustrator": row[3],
            "charter": charter,
        }
    return result


def parse_difficulty_tsv(text: str) -> dict[str, dict[str, float]]:
    """解析 difficulty.tsv。

    每行为曲目 id 与各难度定数，难度数量随曲目而异。

    :param text: difficulty.tsv 的文本内容。
    """
    result = {}
    for row in _rows(text):
        if len(row) < 2:
            continue
        diff = {}
        for index, name in enumerate(DIFF_NAMES):
            if 1 + index >= len(row):
                break
            try:
                diff[name] = float(row[1 + index])
            except ValueError:
                Logger.warning(f"Invalid difficulty value for {row[0]} {name}: {row[1 + index]}")
        result[row[0]] = diff
    return result


def build_song_info(info_text: str, diff_text: str) -> dict[str, dict]:
    """合并两份 TSV 为曲目信息结构。

    :param info_text: info.tsv 的文本内容。
    :param diff_text: difficulty.tsv 的文本内容。
    """
    songs = parse_info_tsv(info_text)
    for song_id, diff in parse_difficulty_tsv(diff_text).items():
        song = songs.setdefault(
            song_id,
            {"name": song_id.split(".")[0], "artist": "", "illustrator": "", "charter": {}},
        )
        song["diff"] = diff
    for song in songs.values():
        song.setdefault("diff", {})
    return songs


def song_info_exists() -> bool:
    """判断曲目信息文件是否已生成。"""
    return song_info_path.exists()


def load_song_info() -> dict[str, dict]:
    """读取曲目信息文件。"""
    with open(song_info_path, "rb") as f:
        return orjson.loads(f.read())


def _as_constant(value) -> float:
    """将定数取值转为浮点数，无法解析者视作该难度缺失。

    5.1 之前的曲目信息将定数原样保留为字符串，缺失的难度写作 "-"，直接转换会中断整表构建。

    :param value: 定数取值。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def is_legacy_song_info(song_info: dict) -> bool:
    """判断曲目信息是否为 5.1 之前的旧版结构。

    旧版以归一化后的小写曲目 id 为键，与存档中的原始 id 无法对应，即便定数容错也只会
    得出全空的成绩，故须在使用前识别并要求重建。判据取旧版独有的 composer 字段与
    字符串定数两项，命中其一即可认定。

    :param song_info: 曲目信息结构。
    """
    for info in song_info.values():
        if "composer" in info:
            return True
        if any(not isinstance(value, (int, float)) for value in info.get("diff", {}).values()):
            return True
    return False


def to_difficulty_table(song_info: dict) -> dict[str, list[float]]:
    """转换为 countRks 所需的定数表。

    countRks 以 EZ、HD、IN、AT、Legacy 的下标取值，故列表固定为五位；
    缺失的难度补 0.0，避免其内部因 IndexError 输出告警。

    :param song_info: 曲目信息结构。
    """
    table = {}
    for song_id, info in song_info.items():
        diff = info.get("diff", {})
        table[song_id] = [_as_constant(diff.get(name, 0.0)) for name in DIFF_NAMES] + [0.0]
    return table


def match_song(song_info: dict, query: str) -> tuple[str, dict] | None:
    """按曲名匹配曲目，两侧均先归一化。

    :param song_info: 曲目信息结构。
    :param query: 用户输入的曲名。
    """
    normalized = remove_punctuations(query)
    if not normalized:
        return None
    for song_id, info in song_info.items():
        if remove_punctuations(info.get("name", "")) == normalized:
            return song_id, info
    return None


def illustration_path(song_id: str) -> Path | None:
    """取曲绘路径，不存在时返回 None。

    :param song_id: 曲目 id。
    """
    path = illustration_dir / f"{song_id}.png"
    return path if path.exists() else None


def _local_version() -> str:
    """读取本地记录的资源版本号。"""
    if not version_path.exists():
        return ""
    return version_path.read_text(encoding="utf-8").strip()


async def _download_illustrations(song_ids: list[str]) -> None:
    """下载缺失的曲绘。

    :param song_ids: 曲目 id 列表。
    """
    illustration_dir.mkdir(parents=True, exist_ok=True)
    known = set(song_ids)
    # 旧版本按归一化的小写 id 命名，与新键无法对应；此处按新键集合清理，旧文件自然落入待删之列。
    for path in illustration_dir.iterdir():
        if path.is_file() and path.stem not in known:
            path.unlink()

    for song_id in song_ids:
        target = illustration_dir / f"{song_id}.png"
        if target.exists():
            continue
        try:
            downloaded = await download(ILLUSTRATION_URL.format(song_id=song_id), f"{song_id}.png")
            if downloaded:
                shutil.move(downloaded, target)
        except Exception:
            Logger.warning(f"Failed to download illustration for {song_id}.")


async def update_assets(update_illustration: bool = True) -> bool:
    """更新曲目信息与曲绘。

    :param update_illustration: 是否一并更新曲绘。
    :return: 是否更新成功。
    """
    try:
        remote_version = (await get_url(VERSION_URL, 200)).strip()
    except Exception:
        Logger.exception()
        return False

    # 版本闸门：版本未变且元数据已就位时跳过重建，但仍走一遍曲绘补全，
    # 以便修复上次中断留下的缺口。
    if remote_version and remote_version == _local_version() and song_info_exists():
        Logger.info(f"Phigros resource already at version {remote_version}, skipping metadata rebuild.")
        song_info = load_song_info()
    else:
        try:
            info_text = await get_url(INFO_TSV_URL, 200)
            diff_text = await get_url(DIFF_TSV_URL, 200)
        except Exception:
            Logger.exception()
            return False

        song_info = build_song_info(info_text, diff_text)
        if not song_info:
            Logger.error("Fetched empty song info from remote resource.")
            return False

        pgr_assets_path.mkdir(parents=True, exist_ok=True)
        temp_path = f"{random_cache_path()}.json"
        with open(temp_path, "wb") as f:
            f.write(orjson.dumps(song_info, option=orjson.OPT_INDENT_2))
        shutil.move(temp_path, song_info_path)

    if update_illustration:
        await _download_illustrations(list(song_info))
        Logger.success("Phigros illustrations download completed.")

    version_path.write_text(remote_version, encoding="utf-8")
    Logger.success(f"Phigros assets updated to version {remote_version}.")
    return True
