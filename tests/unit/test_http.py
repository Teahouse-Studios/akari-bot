"""core.utils.http HTTP 工具单元测试（纯函数部分）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from core.tester import func_case, Tester


def _test_url_pattern_match():
    """url_pattern: 应匹配标准 URL"""
    try:
        from core.utils.http import url_pattern

        urls = [
            "https://example.com",
            "http://test.org/path",
            "https://api.example.com/v1/data?key=value",
        ]
        for url in urls:
            if not url_pattern.search(url):
                return False
        return True
    except Exception:
        return False


def _test_url_pattern_no_match():
    """url_pattern: 不应匹配普通文本"""
    try:
        from core.utils.http import url_pattern

        texts = ["hello world", "just some text", "no_url_here"]
        for text in texts:
            if url_pattern.search(text):
                return False
        return True
    except Exception:
        return False


async def _test_private_ip_check_blocks_non_global():
    """private_ip_check: 应拒绝全部非公网 IP 网段"""
    try:
        from core.utils.http import private_ip_check

        non_global_ips = [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "172.20.0.1",
            "172.31.255.255",
            "192.168.1.1",
            "169.254.0.1",
            "198.18.0.1",
            "0.0.0.0",
            "::",
            "::1",
        ]
        for ip in non_global_ips:
            try:
                await private_ip_check(f"http://[{ip}]/" if ":" in ip else f"http://{ip}/")
                return False
            except ValueError:
                pass
        return True
    except Exception:
        return False


async def _test_private_ip_check_blocks_mapped_ipv6():
    """private_ip_check: IPv4-mapped IPv6 不应绕过私网检查"""
    try:
        from core.utils.http import private_ip_check

        try:
            await private_ip_check("http://[::ffff:127.0.0.1]/")
            return False
        except ValueError:
            return True
    except Exception:
        return False


async def _test_private_ip_check_checks_all_dns_results():
    """private_ip_check: DNS 任一结果非公网时均应拒绝"""
    try:
        import core.utils.http as http_module

        resolver = AsyncMock(return_value={"8.8.8.8", "127.0.0.1"})
        with patch.object(http_module, "_resolve_hostname", resolver):
            try:
                await http_module.private_ip_check("https://mixed.example/path")
                return False
            except ValueError:
                pass
        resolver.assert_awaited_once_with("mixed.example", 443)
        return True
    except Exception:
        return False


async def _test_private_ip_check_allows_global_dns_results():
    """private_ip_check: DNS 全部为公网地址时应放行"""
    try:
        import core.utils.http as http_module

        resolver = AsyncMock(return_value={"8.8.8.8", "2001:4860:4860::8888"})
        with patch.object(http_module, "_resolve_hostname", resolver):
            await http_module.private_ip_check("https://public.example/path")
        resolver.assert_awaited_once_with("public.example", 443)
        return True
    except Exception:
        return False


async def _test_private_ip_check_blocks_empty_dns_results():
    """private_ip_check: DNS 未返回地址时应失败关闭"""
    try:
        import core.utils.http as http_module

        resolver = AsyncMock(return_value=set())
        with patch.object(http_module, "_resolve_hostname", resolver):
            try:
                await http_module.private_ip_check("https://empty.example/path")
                return False
            except ValueError:
                pass
        resolver.assert_awaited_once_with("empty.example", 443)
        return True
    except Exception:
        return False


async def _test_request_url_checks_redirect_before_sending():
    """request_url: 重定向到私网时应在第二跳发送前拒绝"""
    try:
        import core.utils.http as http_module

        original_async_client = httpx.AsyncClient
        sent_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent_urls.append(str(request.url))
            if request.url.host == "public.example":
                return httpx.Response(302, headers={"Location": "http://private.example/secret"})
            return httpx.Response(200, text="private response must not be sent")

        transport = httpx.MockTransport(handler)

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original_async_client(*args, **kwargs)

        async def resolver(hostname: str, port: int) -> set[str]:
            del port
            return {"8.8.8.8"} if hostname == "public.example" else {"127.0.0.1"}

        with (
            patch.object(http_module, "CoreConfig", SimpleNamespace(allow_request_private_ip=False)),
            patch.object(http_module, "Info", SimpleNamespace(http_mock_enabled=False)),
            patch.object(http_module, "_resolve_hostname", resolver),
            patch.object(http_module.httpx, "AsyncClient", client_factory),
        ):
            try:
                await http_module.request_url("http://public.example/start", "GET", attempt=1)
                return False
            except ValueError:
                pass

        return sent_urls == ["http://public.example/start"]
    except Exception:
        return False


async def _test_request_url_private_ip_opt_outs():
    """request_url: 请求级和全局私网放行开关应保持有效"""
    try:
        import core.utils.http as http_module

        original_async_client = httpx.AsyncClient
        sent_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent_urls.append(str(request.url))
            return httpx.Response(200, text="ok")

        transport = httpx.MockTransport(handler)

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original_async_client(*args, **kwargs)

        with (
            patch.object(http_module, "Info", SimpleNamespace(http_mock_enabled=False)),
            patch.object(http_module.httpx, "AsyncClient", client_factory),
        ):
            with patch.object(http_module, "CoreConfig", SimpleNamespace(allow_request_private_ip=False)):
                result_by_request = await http_module.request_url(
                    "http://127.0.0.1/request", "GET", attempt=1, request_private_ip=True
                )
            with patch.object(http_module, "CoreConfig", SimpleNamespace(allow_request_private_ip=True)):
                result_by_config = await http_module.request_url("http://127.0.0.1/config", "GET", attempt=1)

        return result_by_request == "ok" and result_by_config == "ok" and len(sent_urls) == 2
    except Exception:
        return False


@func_case
async def test_http(tester: Tester):
    """core.utils.http: HTTP 工具纯函数测试"""
    await tester.test(_test_url_pattern_match, "url_pattern 匹配 URL 测试")
    await tester.test(_test_url_pattern_no_match, "url_pattern 不匹配文本测试")
    await tester.test(_test_private_ip_check_blocks_non_global, "private_ip_check 拒绝非公网 IP 测试")
    await tester.test(_test_private_ip_check_blocks_mapped_ipv6, "private_ip_check 拒绝 IPv4-mapped IPv6 测试")
    await tester.test(_test_private_ip_check_checks_all_dns_results, "private_ip_check 检查全部 DNS 结果测试")
    await tester.test(_test_private_ip_check_allows_global_dns_results, "private_ip_check 放行公网 DNS 结果测试")
    await tester.test(_test_private_ip_check_blocks_empty_dns_results, "private_ip_check 拒绝空 DNS 结果测试")
    await tester.test(_test_request_url_checks_redirect_before_sending, "request_url 重定向逐跳检查测试")
    await tester.test(_test_request_url_private_ip_opt_outs, "request_url 私网放行开关测试")
    return tester
