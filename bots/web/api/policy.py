"""WebUI 策略内容接口：全局 URL 审计名单与本地过滤词库。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, Query, Request
from fastapi.responses import Response

from bots.web.client import app, get_client_ip, limiter
from core.builtins.filter import (
    FILTER_WORD_SUFFIX,
    MAX_FILTER_CATEGORIES,
    MAX_FILTER_FILE_BYTES,
    MAX_FILTER_WORDS_PER_CATEGORY,
    MAX_FILTER_WORD_LENGTH,
    FilterWordError,
    append_filter_words,
    category_path,
    delete_filter_category,
    list_categories,
    read_filter_words,
    reload_filter_words,
    remove_filter_words,
    write_filter_words,
)
from core.constants.path import filter_words_path
from core.logger import Logger
from core.queue.contracts import ServerAPI
from core.utils.url_audit import (
    MAX_FILE_BYTES,
    MAX_REGEX_RULES,
    MAX_RULE_LENGTH,
    MAX_RULES,
    MAX_URL_LENGTH,
    GlobalURLAllowlist,
    GlobalURLBlocklist,
    URLRule,
    URLRuleError,
    evaluate_url_policy,
    normalize_url,
    parse_rule,
)
from .auth import verify_jwt

ROOT_DIR = Path(__file__).parent.parent.parent.parent

# 名单名与核心实现的对应关系，同时用作接口路径参数取值。
URL_AUDIT_LISTS = {
    "allowlist": GlobalURLAllowlist,
    "blocklist": GlobalURLBlocklist,
}

REVISION_LENGTH = 16
MISSING_REVISION = "missing"


def _revision_of(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:REVISION_LENGTH]


def _file_meta(path: Path) -> dict:
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "revision": MISSING_REVISION, "size": 0, "updated_at": None}
    return {
        "exists": True,
        "revision": _revision_of(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}"),
        "size": stat.st_size,
        "updated_at": stat.st_mtime,
    }


def _display_path(path: Path) -> str:
    try:
        return f"./{path.resolve().relative_to(ROOT_DIR).as_posix()}"
    except ValueError:
        return str(path)


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid_body")
    return body


def _assert_revision(expected, current: str) -> None:
    if not isinstance(expected, str) or not expected:
        return
    if expected != current:
        raise HTTPException(
            status_code=409,
            detail="revision_mismatch",
            headers={"X-Policy-Revision": current},
        )


def _resolve_list(list_name: str):
    target = URL_AUDIT_LISTS.get(list_name)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown_list")
    return target


def _dump_rule(rule: URLRule) -> dict:
    return {
        "value": rule.value,
        "serialized": rule.serialized,
        "regex": rule.is_regex,
        "source": rule.source,
    }


def _scan_rule_file(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return 0, 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return 0, 0
    valid = 0
    invalid = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            parse_rule(stripped)
        except URLRuleError:
            invalid += 1
        else:
            valid += 1
    return valid, invalid


def _dump_url_list(list_name: str) -> dict:
    target = _resolve_list(list_name)
    builtin_meta = _file_meta(target.builtin_path)
    user_meta = _file_meta(target.user_path)
    builtin_count, builtin_invalid = _scan_rule_file(target.builtin_path)
    user_count, user_invalid = _scan_rule_file(target.user_path)

    return {
        "name": list_name,
        "revision": _revision_of(f"url-audit:{list_name}", builtin_meta["revision"], user_meta["revision"]),
        "files": [
            {
                "source": "global",
                "writable": False,
                "path": _display_path(target.builtin_path),
                "rule_count": builtin_count,
                "invalid_lines": builtin_invalid,
                "ignored": builtin_meta["exists"] and builtin_meta["size"] > MAX_FILE_BYTES,
                **builtin_meta,
            },
            {
                "source": "user",
                "writable": True,
                "path": _display_path(target.user_path),
                "rule_count": user_count,
                "invalid_lines": user_invalid,
                "ignored": user_meta["exists"] and user_meta["size"] > MAX_FILE_BYTES,
                **user_meta,
            },
        ],
        "rules": [_dump_rule(rule) for rule in target.rules()],
        # 供前端做整体替换（PUT）时原样回传，保留用户文件的书写顺序。
        "user_rules": [rule.serialized for rule in target.user_rules()],
        "limits": {
            "max_rules": MAX_RULES,
            "max_regex_rules": MAX_REGEX_RULES,
            "max_rule_length": MAX_RULE_LENGTH,
            "max_url_length": MAX_URL_LENGTH,
            "max_file_bytes": MAX_FILE_BYTES,
        },
    }


def _url_audit_revision() -> str:
    return _revision_of(
        "url-audit",
        _dump_url_list("allowlist")["revision"],
        _dump_url_list("blocklist")["revision"],
    )


def _filter_word_files() -> list[Path]:
    if not filter_words_path.is_dir():
        return []
    return [path for path in sorted(filter_words_path.glob(f"*{FILTER_WORD_SUFFIX}")) if path.is_file()]


def _filter_words_revision() -> str:
    parts = ["filter-words"]
    for path in _filter_word_files():
        parts.append(f"{path.name}:{_file_meta(path)['revision']}")
    return _revision_of(*parts)


def _dump_category(category: str, words: list[str]) -> dict:
    path = category_path(category)
    return {
        "name": category,
        "label": f"local_{category}",
        "file": path.name,
        "count": len(words),
        "words": words,
        **_file_meta(path),
    }


def _dump_filter_words() -> dict:
    categories = list_categories()
    return {
        "revision": _filter_words_revision(),
        "directory": _display_path(filter_words_path),
        "categories": [_dump_category(name, words) for name, words in categories.items()],
        "limits": {
            "max_categories": MAX_FILTER_CATEGORIES,
            "max_words_per_category": MAX_FILTER_WORDS_PER_CATEGORY,
            "max_word_length": MAX_FILTER_WORD_LENGTH,
            "max_file_bytes": MAX_FILTER_FILE_BYTES,
        },
    }


def _filter_category_response(category: str, changed: bool) -> dict:
    words = read_filter_words(category)
    return {
        "changed": changed,
        "revision": _filter_words_revision(),
        "category": None if words is None else _dump_category(category, words),
    }


async def _sync_filter_words() -> bool:
    reload_filter_words()
    try:
        return bool(await ServerAPI.reload_filter_words())
    except Exception:
        Logger.exception("[WebUI] Failed to reload filter words in the bot process: ")
        return False


@app.get("/api/policy/revision")
@limiter.limit("120/minute")
async def get_policy_revision(request: Request):
    try:
        verify_jwt(request)

        url_audit = {
            "allowlist": _dump_url_list("allowlist")["revision"],
            "blocklist": _dump_url_list("blocklist")["revision"],
        }
        filter_words = _filter_words_revision()
        return {
            "revision": _revision_of("policy", url_audit["allowlist"], url_audit["blocklist"], filter_words),
            "url_audit": url_audit,
            "filter_words": filter_words,
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/url-audit")
@limiter.limit("60/minute")
async def get_url_audit(request: Request, revision: str = Query(None)):
    try:
        verify_jwt(request)

        payload = {
            "revision": _url_audit_revision(),
            "allowlist": _dump_url_list("allowlist"),
            "blocklist": _dump_url_list("blocklist"),
        }
        if revision and revision == payload["revision"]:
            return Response(status_code=304)
        return payload
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/url-audit/query")
@limiter.limit("60/minute")
async def query_url_rule(request: Request, url: str = Query(...)):
    """查询某个 URL 的命中情况，供前端做规则试算。"""
    try:
        verify_jwt(request)

        payload = {
            "url": url,
            "normalized": None,
            "valid": True,
            "allowed": False,
            "blocked": False,
            "matches": {"allowlist": [], "blocklist": []},
        }
        try:
            payload["normalized"] = normalize_url(url)
        except URLRuleError as exc:
            payload["valid"] = False
            payload["reason"] = exc.reason
            return payload

        decision = evaluate_url_policy(url)
        payload["allowed"] = decision.allowed
        payload["blocked"] = decision.blocked
        payload["matches"] = {
            "allowlist": [_dump_rule(rule) for rule in GlobalURLAllowlist.matching_rules(url)],
            "blocklist": [_dump_rule(rule) for rule in GlobalURLBlocklist.matching_rules(url)],
        }
        return payload
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/url-audit/{list_name}")
@limiter.limit("60/minute")
async def get_url_audit_list(request: Request, list_name: str, revision: str = Query(None)):
    """读取单份 URL 名单；``revision`` 与当前一致时返回 304 空响应。"""
    try:
        verify_jwt(request)

        payload = _dump_url_list(list_name)
        if revision and revision == payload["revision"]:
            return Response(status_code=304)
        return payload
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/url-audit/{list_name}/rules")
@limiter.limit("30/minute")
async def add_url_rule(request: Request, list_name: str):
    """向用户自定义名单追加一条规则（已存在时 ``changed`` 为 false）。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)
        target = _resolve_list(list_name)

        body = await _json_body(request)
        value = body.get("value")
        regex = body.get("regex", False)
        if not isinstance(value, str) or not value.strip() or not isinstance(regex, bool):
            raise HTTPException(status_code=400, detail="invalid_body")
        _assert_revision(body.get("revision"), _dump_url_list(list_name)["revision"])

        try:
            added = target.add_user_rule(value, is_regex=regex)
        except URLRuleError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        Logger.info(f"[WebUI] {ip} added a rule to the global URL {list_name}: {value}")
        return {"changed": added, **_dump_url_list(list_name)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.put("/api/url-audit/{list_name}/rules")
@limiter.limit("30/minute")
async def replace_url_rules(request: Request, list_name: str):
    """整体替换用户自定义名单；``rules`` 为空列表即清空用户规则。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)
        target = _resolve_list(list_name)

        body = await _json_body(request)
        rules = body.get("rules")
        if not isinstance(rules, list) or not all(isinstance(item, str) for item in rules):
            raise HTTPException(status_code=400, detail="invalid_body")
        _assert_revision(body.get("revision"), _dump_url_list(list_name)["revision"])

        try:
            written = target.replace_user_rules(rules)
        except URLRuleError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        Logger.info(f"[WebUI] {ip} replaced the global URL {list_name} user rules ({len(written)} rules)")
        return {"changed": True, **_dump_url_list(list_name)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/url-audit/{list_name}/rules")
@limiter.limit("30/minute")
async def remove_url_rule(
    request: Request,
    list_name: str,
    value: str = Query(...),
    regex: bool = Query(False),
    revision: str = Query(None),
):
    """从用户自定义名单删除一条规则（不存在时 ``changed`` 为 false）。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)
        target = _resolve_list(list_name)
        _assert_revision(revision, _dump_url_list(list_name)["revision"])

        try:
            removed = target.remove_user_rule(value, is_regex=regex)
        except URLRuleError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        Logger.info(f"[WebUI] {ip} removed a rule from the global URL {list_name}: {value}")
        return {"changed": removed, **_dump_url_list(list_name)}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


async def _write_filter_category(ip: str, category: str, words: list[str]) -> dict:
    try:
        written = write_filter_words(category, words)
    except FilterWordError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from None

    synced = await _sync_filter_words()
    Logger.info(f"[WebUI] {ip} wrote the filter word category {category} ({len(written)} words)")
    return {**_filter_category_response(category, True), "runtime_synced": synced}


@app.get("/api/filter-words")
@limiter.limit("60/minute")
async def get_filter_words(request: Request, revision: str = Query(None)):
    """读取全部过滤词库分类；``revision`` 与当前一致时返回 304 空响应。"""
    try:
        verify_jwt(request)

        payload = _dump_filter_words()
        if revision and revision == payload["revision"]:
            return Response(status_code=304)
        return payload
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.get("/api/filter-words/{category}")
@limiter.limit("60/minute")
async def get_filter_word_category(request: Request, category: str):
    """读取单个分类的词条。"""
    try:
        verify_jwt(request)

        words = read_filter_words(category)
        if words is None:
            raise HTTPException(status_code=404, detail="category_not_found")
        return {
            "revision": _filter_words_revision(),
            "category": _dump_category(category, words),
        }
    except HTTPException as e:
        raise e
    except FilterWordError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from None
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.put("/api/filter-words/{category}")
@limiter.limit("30/minute")
async def replace_filter_word_category(request: Request, category: str):
    """整体替换分类词条；``words`` 为空列表即删除该分类。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await _json_body(request)
        words = body.get("words")
        if not isinstance(words, list) or not all(isinstance(item, str) for item in words):
            raise HTTPException(status_code=400, detail="invalid_body")
        _assert_revision(body.get("revision"), _filter_words_revision())

        return await _write_filter_category(ip, category, words)
    except HTTPException as e:
        raise e
    except FilterWordError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from None
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/filter-words/{category}")
@limiter.limit("30/minute")
async def delete_filter_word_category(request: Request, category: str, revision: str = Query(None)):
    """删除整个分类文件（不存在时 ``changed`` 为 false）。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)
        _assert_revision(revision, _filter_words_revision())

        try:
            removed = delete_filter_category(category)
        except FilterWordError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        synced = await _sync_filter_words() if removed else True
        Logger.info(f"[WebUI] {ip} deleted the filter word category {category}: {removed}")
        return {**_filter_category_response(category, removed), "runtime_synced": synced}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.post("/api/filter-words/{category}/words")
@limiter.limit("30/minute")
async def append_filter_word_category(request: Request, category: str):
    """向分类追加词条（分类不存在时创建），按首次出现顺序去重。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)

        body = await _json_body(request)
        words = body.get("words")
        if not isinstance(words, list) or not words or not all(isinstance(item, str) for item in words):
            raise HTTPException(status_code=400, detail="invalid_body")
        _assert_revision(body.get("revision"), _filter_words_revision())

        try:
            merged = append_filter_words(category, words)
        except FilterWordError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        synced = await _sync_filter_words()
        Logger.info(f"[WebUI] {ip} appended words to the filter word category {category} ({len(merged)} words)")
        return {**_filter_category_response(category, True), "runtime_synced": synced}
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")


@app.delete("/api/filter-words/{category}/words")
@limiter.limit("30/minute")
async def remove_filter_word_category(
    request: Request,
    category: str,
    word: list[str] | None = Query(None),
    revision: str = Query(None),
):
    """删除分类中的指定词条（``word`` 可重复传入多次）。"""
    ip = get_client_ip(request)
    try:
        verify_jwt(request)
        targets = [item for item in (word or []) if item.strip()]
        if not targets:
            raise HTTPException(status_code=400, detail="invalid_body")
        _assert_revision(revision, _filter_words_revision())

        try:
            _, removed = remove_filter_words(category, targets)
        except FilterWordError as exc:
            raise HTTPException(status_code=422, detail=exc.reason) from None

        synced = await _sync_filter_words() if removed else True
        Logger.info(f"[WebUI] {ip} removed {removed} words from the filter word category {category}")
        return {
            **_filter_category_response(category, bool(removed)),
            "removed": removed,
            "runtime_synced": synced,
        }
    except HTTPException as e:
        raise e
    except Exception:
        Logger.exception()
        raise HTTPException(status_code=400, detail="Bad request")
