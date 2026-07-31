"""HTTP Mock 工具 - 为需要网络请求的模块提供 mock 支持。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from core.constants.info import Info


def digest_request_body(data: Any) -> str | None:
    """计算请求体的摘要，用于区分同一 URL 上的不同请求。

    部分接口（如 nbnhhsh）以 POST 请求体决定响应内容，仅凭 URL 无法区分，
    回放时会让所有请求都命中同一份录制结果。

    :param data: 请求体，可能为 bytes、str 或可转为字符串的对象。
    :return: 请求体的 SHA256 摘要；请求体为空时返回 None。
    """
    if data is None:
        return None
    if isinstance(data, bytes):
        raw = data
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = repr(data).encode("utf-8")
    if not raw:
        return None
    return hashlib.sha256(raw).hexdigest()


class MockHTTPResponse:
    """模拟 HTTP 响应。"""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
        headers: dict[str, str] | None = None,
        content: bytes = b"",
    ):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}
        self.content = content

    def json(self):
        return self._json

    def read(self) -> bytes:
        """返回响应的二进制内容，对齐 `httpx.Response.read` 的语义。

        `download()` 以 `fmt="read"` 调用 `request_url`，若缺少此方法，
        mock 分支会抛出 `No such method: read`，导致 fixture 无法覆盖下载类请求。

        :return: 响应正文的二进制内容；未录制二进制内容时回退为 text 的 UTF-8 编码。
        """
        if self.content:
            return self.content
        return self.text.encode("utf-8")

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}")

    def __repr__(self):
        return f"MockHTTPResponse(status_code={self.status_code})"


@dataclass
class _Registration:
    """一条 mock 规则。method 与 body_digest 为 None 时表示不限。"""

    pattern: re.Pattern
    response: MockHTTPResponse
    method: str | None = None
    body_digest: str | None = None

    def matches(self, url: str, method: str | None, body_digest: str | None) -> bool:
        if not self.pattern.search(url):
            return False
        if self.method is not None and method is not None and self.method.upper() != method.upper():
            return False
        if self.body_digest is not None and self.body_digest != body_digest:
            return False
        return True

    @property
    def specificity(self) -> int:
        """规则的具体程度，用于在多条命中时择优。"""
        return (2 if self.body_digest is not None else 0) + (1 if self.method is not None else 0)


class HTTPMock:
    """HTTP 请求 mock 管理器。

    使用方式：
        # 注册 mock
        HTTPMock.register("https://api.example.com/data", MockHTTPResponse(json_data={"key": "value"}))
        HTTPMock.register(r"https://api\\.example\\.com/.*", MockHTTPResponse(text="pattern match"))

        # 获取 mock 响应
        resp = HTTPMock.get_response("https://api.example.com/data")

        # 清除
        HTTPMock.clear()

    同一 URL 可注册多条规则：附带 method 与请求体摘要的规则优先于宽泛规则，
    以便区分 POST 接口上请求体不同的调用。
    """

    _responses: list[_Registration] = []

    @classmethod
    def register(
        cls,
        url_pattern: str,
        response: MockHTTPResponse,
        method: str | None = None,
        body_digest: str | None = None,
    ):
        """注册 URL 模式的 mock 响应。

        :param url_pattern: URL 正则表达式模式
        :param response: 模拟的响应对象
        :param method: 限定的 HTTP 方法，None 表示不限
        :param body_digest: 限定的请求体摘要，None 表示不限
        """
        cls._responses.append(_Registration(re.compile(url_pattern), response, method, body_digest))

    @classmethod
    def register_exact(
        cls,
        url: str,
        response: MockHTTPResponse,
        method: str | None = None,
        body_digest: str | None = None,
    ):
        """注册精确 URL 的 mock 响应。

        :param url: 精确的 URL
        :param response: 模拟的响应对象
        :param method: 限定的 HTTP 方法，None 表示不限
        :param body_digest: 限定的请求体摘要，None 表示不限
        """
        cls.register(re.escape(url), response, method, body_digest)

    @classmethod
    def clear(cls):
        """清除所有 mock。"""
        cls._responses.clear()

    @classmethod
    def enable(cls, strict: bool | None = None):
        """启用 HTTP mock。

        :param strict: 是否禁止未命中的请求回落到真实网络。None 表示保持当前设置。
        """
        Info.http_mock_enabled = True
        if strict is not None:
            Info.http_mock_strict = strict

    @classmethod
    def disable(cls):
        """禁用 HTTP mock。"""
        Info.http_mock_enabled = False
        Info.http_mock_strict = False

    @classmethod
    def is_enabled(cls) -> bool:
        """检查 mock 是否启用。"""
        return Info.http_mock_enabled

    @classmethod
    def get_response(cls, url: str, method: str | None = None, data: Any = None) -> MockHTTPResponse | None:
        """获取 mock 响应。

        :param url: 请求的 URL
        :param method: 请求方法，用于区分同一 URL 上的不同方法
        :param data: 请求体，用于区分同一 URL 上请求体不同的调用
        :returns: 匹配的 mock 响应，无匹配返回 None
        """
        body_digest = digest_request_body(data)
        best: _Registration | None = None
        for registration in cls._responses:
            if not registration.matches(url, method, body_digest):
                continue
            if best is None or registration.specificity > best.specificity:
                best = registration
        return best.response if best else None

    @classmethod
    def get_all_responses(cls) -> list[tuple[str, MockHTTPResponse]]:
        """获取所有注册的 mock 响应。

        :returns: (模式字符串, 响应) 列表
        """
        return [(r.pattern.pattern, r.response) for r in cls._responses]


__all__ = ["HTTPMock", "MockHTTPResponse", "digest_request_body"]
