"""HTTP Mock 工具 - 为需要网络请求的模块提供 mock 支持。"""

from __future__ import annotations

import re
from typing import Any

from core.constants.info import Info


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

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP {self.status_code}")

    def __repr__(self):
        return f"MockHTTPResponse(status_code={self.status_code})"


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
    """

    _responses: list[tuple[re.Pattern, MockHTTPResponse]] = []

    @classmethod
    def register(cls, url_pattern: str, response: MockHTTPResponse):
        """注册 URL 模式的 mock 响应。

        :param url_pattern: URL 正则表达式模式
        :param response: 模拟的响应对象
        """
        pattern = re.compile(url_pattern)
        cls._responses.append((pattern, response))

    @classmethod
    def register_exact(cls, url: str, response: MockHTTPResponse):
        """注册精确 URL 的 mock 响应。

        :param url: 精确的 URL
        :param response: 模拟的响应对象
        """
        escaped = re.escape(url)
        cls.register(escaped, response)

    @classmethod
    def clear(cls):
        """清除所有 mock。"""
        cls._responses.clear()

    @classmethod
    def enable(cls):
        """启用 HTTP mock。"""
        Info.http_mock_enabled = True

    @classmethod
    def disable(cls):
        """禁用 HTTP mock。"""
        Info.http_mock_enabled = False

    @classmethod
    def is_enabled(cls) -> bool:
        """检查 mock 是否启用。"""
        return Info.http_mock_enabled

    @classmethod
    def get_response(cls, url: str) -> MockHTTPResponse | None:
        """获取 mock 响应。

        :param url: 请求的 URL
        :returns: 匹配的 mock 响应，无匹配返回 None
        """
        for pattern, response in cls._responses:
            if pattern.search(url):
                return response
        return None

    @classmethod
    def get_all_responses(cls) -> list[tuple[str, MockHTTPResponse]]:
        """获取所有注册的 mock 响应。

        :returns: (模式字符串, 响应) 列表
        """
        return [(p.pattern, r) for p, r in cls._responses]


__all__ = ["HTTPMock", "MockHTTPResponse"]
