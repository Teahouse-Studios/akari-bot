"""core.utils.http HTTP 工具单元测试（纯函数部分）。"""

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


def _test_private_ip_check_blocks_private():
    """private_ip_check: 应拒绝私有 IP"""
    try:
        from core.utils.http import private_ip_check

        try:
            private_ip_check("http://127.0.0.1/test")
            return False
        except (ValueError, Exception):
            return True
    except Exception:
        return False


def _test_private_ip_regex_match():
    """_matcher_private_ips: 应匹配私有 IP 模式"""
    try:
        from core.utils.http import _matcher_private_ips

        private_ips = [
            "127.0.0.1",
            "10.0.0.1",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.0.1",
        ]
        for ip in private_ips:
            if not _matcher_private_ips.match(ip):
                return False
        return True
    except Exception:
        return False


def _test_private_ip_regex_no_match():
    """_matcher_private_ips: 不应匹配公网 IP"""
    try:
        from core.utils.http import _matcher_private_ips

        public_ips = [
            "8.8.8.8",
            "1.1.1.1",
            "203.0.113.1",
        ]
        for ip in public_ips:
            if _matcher_private_ips.match(ip):
                return False
        return True
    except Exception:
        return False


@func_case
async def test_http(tester: Tester):
    """core.utils.http: HTTP 工具纯函数测试"""
    await tester.test(_test_url_pattern_match, "url_pattern 匹配 URL 测试")
    await tester.test(_test_url_pattern_no_match, "url_pattern 不匹配文本测试")
    await tester.test(_test_private_ip_regex_match, "_matcher_private_ips 匹配私有 IP 测试")
    await tester.test(_test_private_ip_regex_no_match, "_matcher_private_ips 不匹配公网 IP 测试")
    return tester
