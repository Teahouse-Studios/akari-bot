import os
import re
import tempfile
import threading
from collections.abc import Iterable
from pathlib import Path

from core.builtins.filter.protect import get_protected_intervals, is_protected
from core.builtins.message.internal import I18NContext
from core.constants.path import filter_words_path
from core.logger import Logger

# 词库文件约束。WebUI 与命令写入前按此校验，避免把机器人读不动的文件放进目录。
FILTER_WORD_SUFFIX = ".txt"
MAX_FILTER_CATEGORIES = 64
MAX_FILTER_WORDS_PER_CATEGORY = 20000
MAX_FILTER_WORD_LENGTH = 128
MAX_FILTER_FILE_BYTES = 1024 * 1024

# 分类名同时用作文件名，因此限制为字母、数字、下划线与连字符。
_CATEGORY_NAME_PATTERN = re.compile(r"^[0-9A-Za-z_-]{1,64}$")

_write_lock = threading.Lock()


class FilterWordError(ValueError):
    """词库写入失败的原因。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _read_filter_file(file: Path) -> list[str] | None:
    try:
        return [line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError) as exc:
        Logger.warning(f"Failed to load filter words from {file}: {exc}")
        return None


def list_categories() -> dict[str, list[str]]:
    """按文件名排序列出全部分类及其词条（保留文件中的原始顺序）。"""
    categories: dict[str, list[str]] = {}

    if not filter_words_path.is_dir():
        return categories

    for file in sorted(filter_words_path.glob(f"*{FILTER_WORD_SUFFIX}")):
        if not file.is_file():
            continue

        words = _read_filter_file(file)
        if words is not None:
            categories[file.stem] = words

    return categories


def _load_badword_rules() -> dict[str, list[str]]:
    return {f"local_{name}": words for name, words in list_categories().items() if words}


badword_rules = _load_badword_rules()


def reload_filter_words() -> dict[str, list[str]]:
    """重新读取词库并原地替换已加载规则，供写入后立即生效。"""
    rules = _load_badword_rules()
    badword_rules.clear()
    badword_rules.update(rules)
    return badword_rules


def normalize_category(category: str) -> str:
    """校验分类名，非法时抛出 :class:`FilterWordError`。"""
    value = str(category).strip()
    if not _CATEGORY_NAME_PATTERN.fullmatch(value):
        raise FilterWordError("invalid_category")
    return value


def category_path(category: str) -> Path:
    """取分类对应的词库文件路径。"""
    return filter_words_path / f"{normalize_category(category)}{FILTER_WORD_SUFFIX}"


def normalize_words(words: Iterable[str]) -> list[str]:
    """清洗词条：去空白、丢弃空行、按首次出现顺序去重，并校验长度与数量。"""
    normalized: list[str] = []
    seen: set[str] = set()

    for word in words:
        value = str(word).strip()
        if not value or value in seen:
            continue
        if len(value) > MAX_FILTER_WORD_LENGTH:
            raise FilterWordError("word_too_long")
        seen.add(value)
        normalized.append(value)

    if len(normalized) > MAX_FILTER_WORDS_PER_CATEGORY:
        raise FilterWordError("too_many_words")

    return normalized


def read_filter_words(category: str) -> list[str] | None:
    """读取分类的原始词条，文件不存在时返回 None。"""
    path = category_path(category)
    if not path.is_file():
        return None
    return _read_filter_file(path)


def _atomic_write(path: Path, content: str) -> None:
    # 临时文件与目标同目录，确保 os.replace 只在同一文件系统内进行。
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, newline="\n") as file:
            temp_path = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _check_category_quota(path: Path) -> None:
    if path.exists():
        return
    if len(list_categories()) >= MAX_FILTER_CATEGORIES:
        raise FilterWordError("too_many_categories")


def write_filter_words(category: str, words: Iterable[str]) -> list[str]:
    """整体替换分类词条，空列表表示删除该分类；写入后立即重载词库。"""
    path = category_path(category)
    normalized = normalize_words(words)

    with _write_lock:
        if not normalized:
            path.unlink(missing_ok=True)
        else:
            _check_category_quota(path)
            content = "".join(f"{word}\n" for word in normalized)
            if len(content.encode("utf-8")) > MAX_FILTER_FILE_BYTES:
                raise FilterWordError("file_too_large")
            _atomic_write(path, content)
        reload_filter_words()

    return normalized


def append_filter_words(category: str, words: Iterable[str]) -> list[str]:
    """追加词条并按首次出现顺序去重，返回写入后的完整词条。"""
    existing = read_filter_words(category) or []
    return write_filter_words(category, [*existing, *words])


def remove_filter_words(category: str, words: Iterable[str]) -> tuple[list[str], int]:
    """删除指定词条，返回剩余词条与删除数量。"""
    existing = read_filter_words(category)
    if existing is None:
        return [], 0

    targets = {str(word).strip() for word in words if str(word).strip()}
    remaining = [word for word in existing if word not in targets]
    removed = len(existing) - len(remaining)
    if removed:
        write_filter_words(category, remaining)
    return remaining, removed


def delete_filter_category(category: str) -> bool:
    """删除分类文件并重载词库；文件不存在时返回 False。"""
    path = category_path(category)

    with _write_lock:
        if not path.is_file():
            return False
        path.unlink()
        reload_filter_words()

    return True


def _find_badword_matches(content: str) -> list[tuple[int, int, str]]:
    replace_tasks: list[tuple[str, str]] = []
    seen: set[str] = set()

    for label, words in badword_rules.items():
        for word in words:
            word = str(word).strip()

            if not word or word in seen:
                continue

            seen.add(word)
            replace_tasks.append((word, label))

    # 长关键词优先，避免短关键词抢先占用匹配区间。
    replace_tasks.sort(key=lambda item: len(item[0]), reverse=True)

    protected_intervals = get_protected_intervals(content)

    matches: list[tuple[int, int, str]] = []
    replaced_intervals: list[tuple[int, int]] = []

    for word, label in replace_tasks:
        reason = str(I18NContext("check.redacted", reason=label))

        for match in re.finditer(re.escape(word), content):
            start, end = match.start(), match.end()

            # 命中 AT / I18N / KE 结构部分时跳过
            if is_protected(protected_intervals, start, end):
                continue

            # 已经被更长关键词占用的区间不再重复处理。
            if any(
                start < replaced_end and end > replaced_start for replaced_start, replaced_end in replaced_intervals
            ):
                continue

            matches.append((start, end, reason))
            replaced_intervals.append((start, end))

    return matches


def filter_badwords(content: str) -> str:
    """过滤文本中的关键词并返回过滤后的字符串。"""
    matches = _find_badword_matches(content)

    if not matches:
        return content

    # 从后往前替换，避免修改前面的索引。
    matches.sort(key=lambda item: item[0], reverse=True)

    for start, end, replacement in matches:
        content = content[:start] + replacement + content[end:]

    return content


def contain_badwords(content: str) -> bool:
    """检测文本是否包含关键词。"""
    return bool(_find_badword_matches(content))


__all__ = [
    "FilterWordError",
    "append_filter_words",
    "category_path",
    "contain_badwords",
    "delete_filter_category",
    "filter_badwords",
    "list_categories",
    "normalize_category",
    "normalize_words",
    "read_filter_words",
    "reload_filter_words",
    "remove_filter_words",
    "write_filter_words",
]
