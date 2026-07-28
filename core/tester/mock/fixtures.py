"""HTTP Fixture 工具 - 从本地文件加载 mock 响应数据。

使用方式：
    1. 运行 capture_http_fixtures.py 捕获真实响应
    2. 在测试中调用 load_http_fixtures() 加载缓存
    3. HTTPMock 会自动拦截 request_url 中的请求

Fixture 文件存储在 tests/fixtures/http/ 目录下，文件名为 URL 的 hash。
每个文件包含 JSON 格式的响应数据：
{
    "url": "原始 URL",
    "status_code": 200,
    "text": "响应文本",
    "headers": {"Content-Type": "application/json"},
    "content_base64": "二进制内容的 base64 编码"
}
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from core.tester.mock.http import HTTPMock, MockHTTPResponse, digest_request_body

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "http"


def _url_to_filename(url: str, method: str | None = None, body_digest: str | None = None) -> str:
    """将请求特征转换为安全的文件名（使用 SHA256 hash）。

    文件名需覆盖 method 与请求体，否则同一 URL 上请求体不同的调用会互相覆盖。
    """
    key = url
    if method:
        key = f"{method.upper()} {key}"
    if body_digest:
        key = f"{key}#{body_digest}"
    url_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    # 提取域名作为可读前缀
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.hostname or "unknown"
        domain = domain.replace(".", "_")[:30]
    except Exception:
        domain = "unknown"
    return f"{domain}_{url_hash}.json"


def save_fixture(
    url: str,
    status_code: int,
    text: str,
    headers: dict | None = None,
    content: bytes = b"",
    json_data: Any = None,
    method: str | None = None,
    request_body: Any = None,
) -> Path:
    """保存一个 HTTP 响应到 fixture 文件。

    :param url: 请求的 URL
    :param status_code: HTTP 状态码
    :param text: 响应文本
    :param headers: 响应头
    :param content: 原始二进制内容（可选）
    :param json_data: 解析后的 JSON 数据（用于 fmt="json" 的请求）
    :param method: 请求方法，回放时用于区分同一 URL 上的不同方法
    :param request_body: 请求体，回放时用于区分同一 URL 上请求体不同的调用
    :returns: 保存的文件路径
    """
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    body_digest = digest_request_body(request_body)
    filepath = FIXTURE_DIR / _url_to_filename(url, method, body_digest)

    data = {
        "url": url,
        "status_code": status_code,
        "headers": headers or {},
    }
    if method:
        data["method"] = method.upper()
    if body_digest:
        data["request_body_digest"] = body_digest
    if content:
        data["content_base64"] = base64.b64encode(content).decode("ascii")
    if json_data is not None:
        data["json_data"] = json_data

    # text 与 json_data 对 JSON 接口而言是同一份内容的两种形态，同时落盘会让
    # 大响应的语料体积翻倍。此时只保留 json_data，读取时再还原出 text。
    if json_data is None or text != json.dumps(json_data, ensure_ascii=False):
        data["text"] = text

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    return filepath


def load_http_fixtures(fixture_dir: Path | None = None) -> int:
    """从 fixture 目录加载所有 mock 响应到 HTTPMock。

    :param fixture_dir: fixture 目录路径，默认为 tests/fixtures/http/
    :returns: 加载的 fixture 数量
    """
    if fixture_dir is None:
        fixture_dir = FIXTURE_DIR

    if not fixture_dir.exists():
        return 0

    count = 0
    for filepath in fixture_dir.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            url = data.get("url", "")
            if not url:
                continue

            content_bytes = b""
            if "content_base64" in data:
                content_bytes = base64.b64decode(data["content_base64"])

            text = data.get("text")
            if text is None and "json_data" in data:
                # 保存时省略了与 json_data 重复的 text，此处还原，
                # 以便直接读取响应正文的调用方仍能取到内容。
                text = json.dumps(data["json_data"], ensure_ascii=False)

            response = MockHTTPResponse(
                status_code=data.get("status_code", 200),
                text=text or "",
                headers=data.get("headers", {}),
                content=content_bytes,
            )

            # 填充 json_data 以便 fmt="json" 的请求能正确返回
            if "json_data" in data:
                response._json = data["json_data"]
            elif data.get("text"):
                try:
                    response._json = json.loads(data["text"])
                except (json.JSONDecodeError, TypeError):
                    # text 不是合法 JSON（或类型不匹配）时，保持 _json 未设置；
                    # 调用方仍可通过 text/content 使用响应内容。
                    pass

            HTTPMock.register_exact(
                url,
                response,
                method=data.get("method"),
                body_digest=data.get("request_body_digest"),
            )
            count += 1
        except Exception:
            continue

    # 默认禁止回落到真实网络：未录制的 URL 会带着重试与超时（默认 3 次 × 20 秒）
    # 拖慢用例，并让结果随外部服务状态漂移。录制新语料时以环境变量放行。
    HTTPMock.enable(strict=os.environ.get("AKARI_TEST_ALLOW_LIVE_HTTP") != "1")
    return count


def list_fixtures(fixture_dir: Path | None = None) -> list[dict]:
    """列出所有已保存的 fixture。

    :param fixture_dir: fixture 目录路径
    :returns: fixture 信息列表
    """
    if fixture_dir is None:
        fixture_dir = FIXTURE_DIR

    if not fixture_dir.exists():
        return []

    fixtures = []
    for filepath in sorted(fixture_dir.glob("*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            fixtures.append(
                {
                    "file": filepath.name,
                    "url": data.get("url", ""),
                    "status_code": data.get("status_code", 200),
                    "text_length": len(data.get("text", "")),
                }
            )
        except Exception:
            continue

    return fixtures


__all__ = ["save_fixture", "load_http_fixtures", "list_fixtures", "FIXTURE_DIR"]
