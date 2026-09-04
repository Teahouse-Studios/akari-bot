"""core.utils.dirty_check 内容审核系统单元测试。"""

import json
import urllib.parse
from unittest.mock import patch

from core.tester import func_case, Tester


def _test_parse_data_clean():
    """parse_data: 正常文本应返回 status=True"""
    try:
        from core.utils.dirty_check import parse_data

        result = parse_data("Hello World", {})
        return result["status"] is True and result["content"] == "Hello World"
    except Exception:
        return False


def _test_parse_data_empty():
    """parse_data: 空结果应返回原始文本"""
    try:
        from core.utils.dirty_check import parse_data

        result = parse_data("test", {})
        return result["content"] == "test" and result["original"] == "test"
    except Exception:
        return False


def _test_parse_data_protects_at_code():
    """parse_data: AT 码整体豁免，其中的命中词不应被替换"""
    try:
        from core.utils.dirty_check import parse_data

        result = parse_data(
            "hello <AT:123 BADWORD> world",
            {"RiskLevel": "high", "Result": [{"Confidence": 100, "RiskWords": "BADWORD", "Label": "mock"}]},
        )
        return result["status"] is True and result["content"] == "hello <AT:123 BADWORD> world"
    except Exception:
        return False


def _test_parse_data_protects_ke_i18n_structure():
    """parse_data: KE/I18N 的 value 参与过滤，结构与 key 保持原样"""
    try:
        from core.utils.dirty_check import parse_data

        dirty = {"RiskLevel": "high", "Result": [{"Confidence": 100, "RiskWords": "BADWORD", "Label": "mock"}]}

        ke = parse_data("hello [KE:element,key=BADWORD] world", dirty)
        i18n = parse_data("hello {I18N:msg.example,param=BADWORD} world", dirty)

        return (
            ke["status"] is False
            and "BADWORD" not in ke["content"]
            and "[KE:element,key=" in ke["content"]
            and ke["content"].endswith("] world")
            and i18n["status"] is False
            and "BADWORD" not in i18n["content"]
            and "{I18N:msg.example,param=" in i18n["content"]
            and "} world" in i18n["content"]
        )
    except Exception:
        return False


def _test_hash_hmac():
    """hash_hmac: 应返回 base64 编码的 HMAC"""
    try:
        from core.utils.dirty_check import hash_hmac

        result = hash_hmac("secret", "message")
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


async def _test_check_no_keys():
    """check: 无 API 密钥时应跳过检查并返回原始文本"""
    try:
        with patch("core.utils.dirty_check.access_key_id", ""), patch("core.utils.dirty_check.access_key_secret", ""):
            from core.utils.dirty_check import check

            results = await check("Hello World")
            if len(results) != 1:
                return False
            return results[0]["status"] is True and results[0]["content"] == "Hello World"
    except Exception:
        return False


async def _test_check_empty_text():
    """check: 空文本列表应返回空结果"""
    try:
        with patch("core.utils.dirty_check.access_key_id", ""), patch("core.utils.dirty_check.access_key_secret", ""):
            from core.utils.dirty_check import check

            results = await check([])
            return results == []
    except Exception:
        return False


def _test_rickroll():
    """rickroll: 应返回字符串"""
    try:
        from core.utils.dirty_check import rickroll

        result = rickroll()
        return isinstance(result, str) and len(result) > 0
    except Exception:
        return False


async def _test_check_bool_clean_is_false():
    """check_bool: 内容合规时返回 False

    该函数回答的是「是否含有不合规内容」，与 check() 的 status 字段正好相反，
    调用方曾据其旧有的文档把两个分支写反，故在此把语义钉住。
    """
    try:
        with patch("core.utils.dirty_check.access_key_id", ""), patch("core.utils.dirty_check.access_key_secret", ""):
            from core.utils.dirty_check import check_bool

            return (await check_bool("Hello World")) is False
    except Exception:
        return False


async def _test_check_bool_dirty_is_true():
    """check_bool: 含有不合规内容时返回 True"""
    try:
        from core.utils.dirty_check import check_bool

        async def _redacted(*args, **kwargs):
            return [{"content": "<ALL REDACTED:test>", "status": False, "original": "test"}]

        with patch("core.utils.dirty_check.check", _redacted):
            return (await check_bool("test")) is True
    except Exception:
        return False


async def _test_aliyun_split_cache_preserves_result():
    """check: 长文本命中缓存后应保持所有分片的审核结果"""
    try:
        import core.utils.dirty_check as dirty_check
        from core.database.local import DirtyWordCache

        class FakeResponse:
            status_code = 200
            text = ""

            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

        class FakeClient:
            calls = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, *args, **kwargs):
                type(self).calls += 1
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                content = json.loads(query["ServiceParameters"][0])["content"]
                if content.startswith("bad"):
                    data = {
                        "RiskLevel": "high",
                        "Result": [{"Confidence": 100, "RiskWords": "bad", "Label": "mock"}],
                    }
                else:
                    data = {"RiskLevel": "none", "Result": []}
                return FakeResponse({"Code": 200, "Data": data})

        text = "bad" + "a" * 597 + "z"
        namespace = f"{dirty_check.ALIYUN_BACKEND}:moderation-plus-v2"
        hash_id = DirtyWordCache.make_hash(text, namespace)
        await DirtyWordCache.filter(hash_id=hash_id).delete()

        with (
            patch.object(dirty_check, "access_key_id", "id"),
            patch.object(dirty_check, "access_key_secret", "secret"),
            patch.object(dirty_check, "use_textscan_v1", False),
            patch.object(dirty_check.httpx, "AsyncClient", FakeClient),
        ):
            first = await dirty_check.check(text, force=True)
            second = await dirty_check.check(text, force=True)
            cache = await DirtyWordCache.check(text, namespace=namespace)

        return (
            first[0]["status"] is False
            and second[0]["status"] is False
            and FakeClient.calls == 2
            and cache is not None
            and len(cache.result[dirty_check.ALIYUN_SPLIT_CACHE_KEY]) == 2
        )
    except Exception:
        return False


def _test_aliyun_cache_namespace_isolated():
    """DirtyWordCache: 阿里云 v1 与 v2 的缓存应隔离"""
    try:
        import core.utils.dirty_check as dirty_check

        with patch.object(dirty_check, "use_textscan_v1", True):
            v1_namespace = dirty_check.dirty_word_cache_namespace(dirty_check.ALIYUN_BACKEND)
        with patch.object(dirty_check, "use_textscan_v1", False):
            v2_namespace = dirty_check.dirty_word_cache_namespace(dirty_check.ALIYUN_BACKEND)
        return v1_namespace != v2_namespace
    except Exception:
        return False


@func_case
async def test_dirty_check(tester: Tester):
    """core.utils.dirty_check: 内容审核系统测试"""
    await tester.test(_test_parse_data_clean, "parse_data 正常文本测试")
    await tester.test(_test_parse_data_empty, "parse_data 空结果测试")
    await tester.test(_test_parse_data_protects_at_code, "parse_data AT 码豁免测试")
    await tester.test(_test_parse_data_protects_ke_i18n_structure, "parse_data KE/I18N 结构与 value 过滤测试")
    await tester.test(_test_hash_hmac, "hash_hmac 测试")
    await tester.test(_test_check_no_keys, "check 无密钥跳过测试")
    await tester.test(_test_check_empty_text, "check 空文本测试")
    await tester.test(_test_rickroll, "rickroll 测试")
    await tester.test(_test_check_bool_clean_is_false, "check_bool 合规返回假测试")
    await tester.test(_test_check_bool_dirty_is_true, "check_bool 不合规返回真测试")
    await tester.test(_test_aliyun_split_cache_preserves_result, "阿里云长文本分片缓存测试")
    await tester.test(_test_aliyun_cache_namespace_isolated, "阿里云缓存版本隔离测试")
    return tester
