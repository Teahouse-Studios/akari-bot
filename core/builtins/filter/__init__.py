import re

from core.builtins.filter.protect import get_protected_intervals, is_protected
from core.builtins.message.internal import I18NContext
from core.constants.path import bad_words_path
from core.logger import Logger


def _load_badword_rules() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}

    if not bad_words_path.is_dir():
        return rules

    for file in sorted(bad_words_path.glob("*.txt")):
        if not file.is_file():
            continue

        label = f"local_{file.stem}"

        try:
            words = [line.strip() for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, UnicodeDecodeError) as exc:
            Logger.warning(f"Failed to load bad words from {file}: {exc}")
            continue

        if words:
            rules[label] = words

    return rules


badword_rules = _load_badword_rules()


def _find_badword_matches(content: str) -> list[tuple[int, int, str]]:
    """查找文本中的关键词命中位置。"""
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
    """检测文本是否包含关键词。

    命中关键词返回 True，否则返回 False。
    """
    return bool(_find_badword_matches(content))


__all__ = ["contain_badwords", "filter_badwords"]
