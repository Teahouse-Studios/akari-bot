from __future__ import annotations

import os
import tempfile
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import regex

from core.constants.path import assets_path
from core.logger import Logger

REGEX_RULE_PREFIX = "regex:"
MAX_URL_LENGTH = 4096
MAX_RULE_LENGTH = 500
MAX_RULES = 256
MAX_REGEX_RULES = 64
MAX_FILE_BYTES = 64 * 1024
REGEX_MATCH_TIMEOUT = 0.005
REGEX_BATCH_TIMEOUT = 0.02

_FORBIDDEN_REGEX_TOKENS = ("(?R", "(?0", "(?&", "(?P>", "(?C", "(*", "(?(DEFINE)", "\\g<", "\\g'")
_NUMERIC_BACKREFERENCE = regex.compile(r"(?<!\\)\\[1-9]", regex.VERSION1)
_TEXT_URL_PATTERN = regex.compile(r"""https?://[^\s<>{}\[\]"']+""", regex.IGNORECASE | regex.VERSION1)
_TRAILING_URL_PUNCTUATION = ".,!?;:，。！？；："


class URLRuleError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class URLRule:
    value: str
    is_regex: bool = False
    source: str = "user"

    @property
    def serialized(self) -> str:
        return f"{REGEX_RULE_PREFIX}{self.value}" if self.is_regex else self.value


@dataclass(frozen=True)
class URLPolicyDecision:
    allowed: bool
    blocked: bool


@dataclass(frozen=True)
class _RuleSnapshot:
    literals: frozenset[str]
    regexes: tuple[tuple[URLRule, regex.Pattern], ...]
    rules: tuple[URLRule, ...]


def normalize_url(url: str) -> str:
    value = str(url).strip()
    if not value or len(value) > MAX_URL_LENGTH or any(ord(char) < 32 for char in value):
        raise URLRuleError("invalid_url")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise URLRuleError("invalid_url") from exc
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise URLRuleError("invalid_url")
    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise URLRuleError("invalid_url") from exc
    if not host:
        raise URLRuleError("invalid_url")
    if port == (443 if scheme == "https" else 80):
        port = None
    host_for_netloc = f"[{host}]" if ":" in host else host
    netloc = f"{host_for_netloc}:{port}" if port is not None else host_for_netloc
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, parsed.fragment))


def validate_regex_pattern(pattern: str) -> regex.Pattern:
    value = str(pattern).strip()
    if not value or len(value) > MAX_RULE_LENGTH or any(ord(char) < 32 for char in value):
        raise URLRuleError("invalid_regex")
    if any(token in value for token in _FORBIDDEN_REGEX_TOKENS) or _NUMERIC_BACKREFERENCE.search(value):
        raise URLRuleError("unsafe_regex")
    if "(?P=" in value:
        raise URLRuleError("unsafe_regex")
    try:
        compiled = regex.compile(value, regex.VERSION1)
    except regex.error as exc:
        raise URLRuleError("invalid_regex") from exc
    try:
        if compiled.fullmatch("https://invalid.invalid/url-rule-probe", timeout=REGEX_MATCH_TIMEOUT):
            raise URLRuleError("broad_regex")
    except TimeoutError as exc:
        raise URLRuleError("unsafe_regex") from exc
    return compiled


def serialize_rule(value: str, is_regex: bool = False) -> str:
    if is_regex:
        validate_regex_pattern(value)
        return f"{REGEX_RULE_PREFIX}{str(value).strip()}"
    return normalize_url(value)


def parse_rule(line: str, source: str = "user") -> tuple[URLRule, regex.Pattern | None]:
    value = line.strip()
    if value.startswith(REGEX_RULE_PREFIX):
        pattern = value.removeprefix(REGEX_RULE_PREFIX).strip()
        return URLRule(pattern, is_regex=True, source=source), validate_regex_pattern(pattern)
    normalized = normalize_url(value)
    return URLRule(normalized, source=source), None


def match_regex_rules(url: str, patterns: list[str] | tuple[str, ...]) -> bool:
    try:
        normalized = normalize_url(url)
    except URLRuleError:
        return False
    deadline = time.monotonic() + REGEX_BATCH_TIMEOUT
    for pattern in patterns[:MAX_REGEX_RULES]:
        try:
            compiled = validate_regex_pattern(pattern)
        except URLRuleError:
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            Logger.warning("URL regex batch exceeded its time budget.")
            return False
        try:
            if compiled.fullmatch(normalized, timeout=min(REGEX_MATCH_TIMEOUT, remaining)):
                return True
        except TimeoutError:
            Logger.warning("URL regex timed out and was ignored.")
    return False


class _GlobalURLRuleList:
    directory: Path
    builtin_path: Path
    user_path: Path
    label: str
    _cache_key: tuple | None = None
    _snapshot = _RuleSnapshot(frozenset(), (), ())
    _write_lock = threading.Lock()

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache_key = None
        cls._snapshot = _RuleSnapshot(frozenset(), (), ())

    @classmethod
    def _path_signature(cls, path: Path) -> tuple[str, int | None, int | None]:
        try:
            stat = path.stat()
            return str(path), stat.st_mtime_ns, stat.st_size
        except FileNotFoundError:
            return str(path), None, None

    @classmethod
    def _read_rules(cls, path: Path, source: str) -> list[tuple[URLRule, regex.Pattern | None]]:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                Logger.warning(f"Ignored oversized URL {cls.label} file: {path}")
                return []
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError as exc:
            Logger.warning(f"Failed to read URL {cls.label} file {path}: {exc}")
            return []
        parsed_rules = []
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                parsed_rules.append(parse_rule(stripped, source=source))
            except URLRuleError as exc:
                Logger.warning(f"Ignored invalid URL {cls.label} rule at {path}:{line_number}: {exc.reason}")
        return parsed_rules

    @classmethod
    def _load(cls) -> _RuleSnapshot:
        cache_key = (cls._path_signature(cls.builtin_path), cls._path_signature(cls.user_path))
        if cache_key == cls._cache_key:
            return cls._snapshot

        parsed = cls._read_rules(cls.builtin_path, "global") + cls._read_rules(cls.user_path, "user")
        literals = set()
        regexes = []
        rules = []
        seen = set()
        for rule, compiled in parsed:
            if rule.serialized in seen:
                continue
            if len(rules) >= MAX_RULES:
                Logger.warning(f"Ignored excess URL {cls.label} rules.")
                break
            if rule.is_regex and len(regexes) >= MAX_REGEX_RULES:
                Logger.warning(f"Ignored excess URL {cls.label} regex rules.")
                continue
            seen.add(rule.serialized)
            rules.append(rule)
            if rule.is_regex:
                regexes.append((rule, compiled))
            else:
                literals.add(rule.value)
        cls._cache_key = cache_key
        cls._snapshot = _RuleSnapshot(frozenset(literals), tuple(regexes), tuple(rules))
        return cls._snapshot

    @classmethod
    def matching_rules(cls, url: str) -> list[URLRule]:
        try:
            normalized = normalize_url(url)
        except URLRuleError:
            return []
        snapshot = cls._load()
        matches = [rule for rule in snapshot.rules if not rule.is_regex and rule.value == normalized]
        deadline = time.monotonic() + REGEX_BATCH_TIMEOUT
        for rule, compiled in snapshot.regexes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                Logger.warning(f"Global URL {cls.label} regex batch exceeded its time budget.")
                break
            try:
                if compiled.fullmatch(normalized, timeout=min(REGEX_MATCH_TIMEOUT, remaining)):
                    matches.append(rule)
            except TimeoutError:
                Logger.warning(f"Global URL {cls.label} regex timed out and was ignored.")
        return matches

    @classmethod
    def contains(cls, url: str, *, fail_closed: bool = False) -> bool:
        try:
            normalized = normalize_url(url)
        except URLRuleError:
            return False
        snapshot = cls._load()
        if normalized in snapshot.literals:
            return True
        deadline = time.monotonic() + REGEX_BATCH_TIMEOUT
        for _, compiled in snapshot.regexes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                Logger.warning(f"Global URL {cls.label} regex batch exceeded its time budget.")
                return fail_closed
            try:
                if compiled.fullmatch(normalized, timeout=min(REGEX_MATCH_TIMEOUT, remaining)):
                    return True
            except TimeoutError:
                Logger.warning(f"Global URL {cls.label} regex timed out and was ignored.")
                if fail_closed:
                    return True
        return False

    @classmethod
    def rules(cls) -> tuple[URLRule, ...]:
        return cls._load().rules

    @classmethod
    def _atomic_write(cls, content: str) -> None:
        cls.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=cls.directory, delete=False, newline="\n"
            ) as file:
                temp_path = Path(file.name)
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, cls.user_path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @classmethod
    def add_user_rule(cls, value: str, is_regex: bool = False) -> bool:
        serialized = serialize_rule(value, is_regex=is_regex)
        with cls._write_lock:
            existing = {rule.serialized for rule in cls._load().rules}
            if serialized in existing:
                return False
            if len(existing) >= MAX_RULES:
                raise URLRuleError("too_many_rules")
            if is_regex and sum(rule.is_regex for rule in cls._load().rules) >= MAX_REGEX_RULES:
                raise URLRuleError("too_many_regex")
            try:
                content = cls.user_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                content = ""
            if len(content.encode("utf-8")) + len(serialized.encode("utf-8")) + 1 > MAX_FILE_BYTES:
                raise URLRuleError("file_too_large")
            if content and not content.endswith("\n"):
                content += "\n"
            cls._atomic_write(content + serialized + "\n")
            cls.clear_cache()
            return True

    @classmethod
    def import_user_rules(cls, serialized_rules: Iterable[str]) -> int:
        """将旧存储中的序列化规则幂等迁入用户规则文件。"""
        imported = 0
        for serialized in serialized_rules:
            rule, _ = parse_rule(serialized)
            if cls.add_user_rule(rule.value, is_regex=rule.is_regex):
                imported += 1
        return imported

    @classmethod
    def remove_user_rule(cls, value: str, is_regex: bool = False) -> bool:
        serialized = serialize_rule(value, is_regex=is_regex)
        with cls._write_lock:
            try:
                lines = cls.user_path.read_text(encoding="utf-8").splitlines(keepends=True)
            except FileNotFoundError:
                return False
            removed = False
            retained = []
            for line in lines:
                stripped = line.strip()
                try:
                    current = parse_rule(stripped)[0].serialized if stripped and not stripped.startswith("#") else None
                except URLRuleError:
                    current = None
                if current == serialized:
                    removed = True
                else:
                    retained.append(line)
            if not removed:
                return False
            cls._atomic_write("".join(retained))
            cls.clear_cache()
            return True


class GlobalURLAllowlist(_GlobalURLRuleList):
    directory = assets_path / "url_audit" / "allowlist"
    builtin_path = directory / "global.txt"
    user_path = directory / "user.txt"
    label = "allowlist"

    _cache_key = None
    _snapshot = _RuleSnapshot(frozenset(), (), ())
    _write_lock = threading.Lock()

    @classmethod
    def is_allowed(cls, url: str) -> bool:
        return cls.contains(url)


class GlobalURLBlocklist(_GlobalURLRuleList):
    directory = assets_path / "url_audit" / "blocklist"
    builtin_path = directory / "global.txt"
    user_path = directory / "user.txt"
    label = "blocklist"

    _cache_key = None
    _snapshot = _RuleSnapshot(frozenset(), (), ())
    _write_lock = threading.Lock()

    @classmethod
    def is_blocked(cls, url: str) -> bool:
        return cls.contains(url, fail_closed=True)


def evaluate_url_policy(url: str) -> URLPolicyDecision:
    """统一判定 URL 的全局允许与阻止状态，阻止列表始终优先。"""
    blocked = GlobalURLBlocklist.is_blocked(url)
    return URLPolicyDecision(
        allowed=not blocked and GlobalURLAllowlist.is_allowed(url),
        blocked=blocked,
    )


def redact_blocklisted_urls(text: str, replacement: str) -> str:
    value = str(text)
    if not GlobalURLBlocklist.rules():
        return value
    parts = []
    cursor = 0
    changed = False
    deadline = time.monotonic() + REGEX_BATCH_TIMEOUT
    fail_closed = False
    for match in _TEXT_URL_PATTERN.finditer(value):
        candidate = match.group()
        suffix = ""
        blocked = True if fail_closed else GlobalURLBlocklist.is_blocked(candidate)
        if not blocked and time.monotonic() < deadline:
            while candidate and candidate[-1] in _TRAILING_URL_PUNCTUATION:
                suffix = candidate[-1] + suffix
                candidate = candidate[:-1]
            while candidate.endswith(")") and candidate.count("(") < candidate.count(")"):
                suffix = ")" + suffix
                candidate = candidate[:-1]
            blocked = bool(candidate) and GlobalURLBlocklist.is_blocked(candidate)
        if time.monotonic() >= deadline:
            fail_closed = True
            blocked = True
        if fail_closed and not suffix:
            while candidate and candidate[-1] in _TRAILING_URL_PUNCTUATION:
                suffix = candidate[-1] + suffix
                candidate = candidate[:-1]
            while candidate.endswith(")") and candidate.count("(") < candidate.count(")"):
                suffix = ")" + suffix
                candidate = candidate[:-1]
        if not blocked:
            continue
        parts.extend((value[cursor : match.start()], replacement, suffix))
        cursor = match.end()
        changed = True
    if not changed:
        return value
    parts.append(value[cursor:])
    return "".join(parts)
