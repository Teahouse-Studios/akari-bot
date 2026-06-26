"""core.dirty_check 内容审核系统单元测试。"""

from unittest.mock import patch

from core.tester import func_case, Tester


def _test_parse_data_clean():
    """parse_data: 正常文本应返回 status=True"""
    try:
        from core.dirty_check import parse_data

        result = parse_data("Hello World", {})
        return result["status"] is True and result["content"] == "Hello World"
    except Exception:
        return False


def _test_parse_data_empty():
    """parse_data: 空结果应返回原始文本"""
    try:
        from core.dirty_check import parse_data

        result = parse_data("test", {})
        return result["content"] == "test" and result["original"] == "test"
    except Exception:
        return False


def _test_hash_hmac():
    """hash_hmac: 应返回 base64 编码的 HMAC"""
    try:
        from core.dirty_check import hash_hmac

        result = hash_hmac("secret", "message")
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


async def _test_check_no_keys():
    """check: 无 API 密钥时应跳过检查并返回原始文本"""
    try:
        with patch("core.dirty_check.access_key_id", ""), patch("core.dirty_check.access_key_secret", ""):
            from core.dirty_check import check

            results = await check("Hello World")
            if len(results) != 1:
                return False
            return results[0]["status"] is True and results[0]["content"] == "Hello World"
    except Exception:
        return False


async def _test_check_empty_text():
    """check: 空文本列表应返回空结果"""
    try:
        with patch("core.dirty_check.access_key_id", ""), patch("core.dirty_check.access_key_secret", ""):
            from core.dirty_check import check

            results = await check([])
            return results == []
    except Exception:
        return False


def _test_rickroll():
    """rickroll: 应返回字符串"""
    try:
        from core.dirty_check import rickroll

        result = rickroll()
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


@func_case
async def test_dirty_check(tester: Tester):
    """core.dirty_check: 内容审核系统测试"""
    await tester.test(_test_parse_data_clean, "parse_data 正常文本测试")
    await tester.test(_test_parse_data_empty, "parse_data 空结果测试")
    await tester.test(_test_hash_hmac, "hash_hmac 测试")
    await tester.test(_test_check_no_keys, "check 无密钥跳过测试")
    await tester.test(_test_check_empty_text, "check 空文本测试")
    await tester.test(_test_rickroll, "rickroll 测试")
    return tester
