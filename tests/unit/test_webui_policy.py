"""bots.web.api.policy 单元测试 - URL 审计名单与过滤词库接口。"""

import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import bots.web.api.policy as policy
import core.builtins.filter as filter_words_module
from core.tester import Tester, func_case


class FakeRequest:
    def __init__(self, body=None):
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


def _endpoint(func):
    return inspect.unwrap(func)


async def _call(call) -> tuple[int, object]:
    try:
        result = await call()
    except HTTPException as exc:
        return exc.status_code, exc.detail
    return getattr(result, "status_code", 200), result


async def _url_audit_case() -> bool:
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            global_file = directory / "global.txt"
            user_file = directory / "user.txt"
            global_file.write_text("https://repo.example.test/release\n", encoding="utf-8")
            with (
                patch.object(policy.GlobalURLAllowlist, "builtin_path", global_file),
                patch.object(policy.GlobalURLAllowlist, "user_path", user_file),
                patch.object(policy, "verify_jwt", lambda request: None),
                patch.object(policy, "get_client_ip", lambda request: "test"),
            ):
                policy.GlobalURLAllowlist.clear_cache()

                listing = await _endpoint(policy.get_url_audit_list)(FakeRequest(), "allowlist")
                assert listing["files"][0]["rule_count"] == 1
                assert listing["files"][1]["exists"] is False
                assert [rule["source"] for rule in listing["rules"]] == ["global"]
                assert listing["user_rules"] == []

                status, _ = await _call(
                    lambda: _endpoint(policy.get_url_audit_list)(
                        FakeRequest(), "allowlist", revision=listing["revision"]
                    )
                )
                assert status == 304

                status, detail = await _call(lambda: _endpoint(policy.get_url_audit_list)(FakeRequest(), "unknown"))
                assert (status, detail) == (404, "unknown_list")

                added = await _endpoint(policy.add_url_rule)(
                    FakeRequest({"value": "https://example.test/docs/1", "revision": listing["revision"]}), "allowlist"
                )
                assert added["changed"] is True
                assert user_file.read_text(encoding="utf-8").splitlines() == ["https://example.test/docs/1"]

                again = await _endpoint(policy.add_url_rule)(
                    FakeRequest({"value": "https://example.test/docs/1"}), "allowlist"
                )
                assert again["changed"] is False

                status, detail = await _call(
                    lambda: _endpoint(policy.add_url_rule)(
                        FakeRequest({"value": "https://example.test/docs/1", "revision": "stale"}), "allowlist"
                    )
                )
                assert (status, detail) == (409, "revision_mismatch")

                status, detail = await _call(
                    lambda: _endpoint(policy.add_url_rule)(FakeRequest({"value": "not-a-url"}), "allowlist")
                )
                assert (status, detail) == (422, "invalid_url")

                replaced = await _endpoint(policy.replace_url_rules)(
                    FakeRequest(
                        {
                            "rules": [
                                "https://a.example.test/",
                                r"regex:https://[a-z]+\.example\.test/",
                                "https://a.example.test/",
                            ]
                        }
                    ),
                    "allowlist",
                )
                assert replaced["user_rules"] == ["https://a.example.test/", r"regex:https://[a-z]+\.example\.test/"]

                query = await _endpoint(policy.query_url_rule)(None, url="https://a.example.test/")
                assert query["valid"] is True and query["allowed"] is True and query["blocked"] is False
                assert [rule["serialized"] for rule in query["matches"]["allowlist"]] == [
                    "https://a.example.test/",
                    r"regex:https://[a-z]+\.example\.test/",
                ]

                invalid_query = await _endpoint(policy.query_url_rule)(None, url="ftp://example.test/")
                assert invalid_query["valid"] is False and invalid_query["reason"] == "invalid_url"

                removed = await _endpoint(policy.remove_url_rule)(
                    None, "allowlist", value="https://a.example.test/", regex=False
                )
                assert removed["changed"] is True and removed["user_rules"] == [r"regex:https://[a-z]+\.example\.test/"]

                missing = await _endpoint(policy.remove_url_rule)(
                    None, "allowlist", value="https://a.example.test/", regex=False
                )
                assert missing["changed"] is False

                # 主仓随仓库分发的文件始终只读，接口只改 user.txt。
                assert global_file.read_text(encoding="utf-8") == "https://repo.example.test/release\n"
        return True
    finally:
        policy.GlobalURLAllowlist.clear_cache()


async def _filter_words_case() -> bool:
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(filter_words_module, "filter_words_path", directory),
                patch.object(policy, "filter_words_path", directory),
                patch.object(policy, "verify_jwt", lambda request: None),
                patch.object(policy, "get_client_ip", lambda request: "test"),
                patch.object(policy, "ServerAPI", SimpleNamespace(reload_filter_words=AsyncMock(return_value=True))),
            ):
                listing = await _endpoint(policy.get_filter_words)(FakeRequest())
                assert listing["categories"] == []

                created = await _endpoint(policy.replace_filter_word_category)(
                    FakeRequest({"words": ["示例词A", " 示例词B ", "示例词A"]}), "politics"
                )
                assert created["changed"] is True and created["runtime_synced"] is True
                assert created["category"]["words"] == ["示例词A", "示例词B"]
                assert created["category"]["label"] == "local_politics"
                assert created["category"]["revision"] != "missing"
                assert (directory / "politics.txt").read_text(encoding="utf-8") == "示例词A\n示例词B\n"
                # 写入后词库已就地重载，无需重启即可命中。
                assert filter_words_module.badword_rules == {"local_politics": ["示例词A", "示例词B"]}

                status, _ = await _call(
                    lambda: _endpoint(policy.get_filter_words)(FakeRequest(), revision=created["revision"])
                )
                assert status == 304

                category = await _endpoint(policy.get_filter_word_category)(FakeRequest(), "politics")
                assert category["category"]["count"] == 2

                status, detail = await _call(
                    lambda: _endpoint(policy.get_filter_word_category)(FakeRequest(), "missing")
                )
                assert (status, detail) == (404, "category_not_found")

                appended = await _endpoint(policy.append_filter_word_category)(
                    FakeRequest({"words": ["示例词C", "示例词A"]}), "politics"
                )
                assert appended["category"]["words"] == ["示例词A", "示例词B", "示例词C"]

                status, detail = await _call(
                    lambda: _endpoint(policy.append_filter_word_category)(FakeRequest({"words": []}), "politics")
                )
                assert (status, detail) == (400, "invalid_body")

                removed = await _endpoint(policy.remove_filter_word_category)(
                    None, "politics", word=["示例词B"], revision=appended["revision"]
                )
                assert removed["removed"] == 1 and removed["category"]["words"] == ["示例词A", "示例词C"]

                status, detail = await _call(
                    lambda: _endpoint(policy.replace_filter_word_category)(FakeRequest({"words": ["x"]}), "../evil")
                )
                assert (status, detail) == (422, "invalid_category")
                assert not (directory.parent / "evil.txt").exists()

                deleted = await _endpoint(policy.delete_filter_word_category)(FakeRequest(), "politics")
                assert deleted["changed"] is True and deleted["category"] is None
                assert not (directory / "politics.txt").exists()
                assert filter_words_module.badword_rules == {}
        return True
    finally:
        # 词库是模块级共享状态：退出前按真实目录重载，避免污染其它用例。
        filter_words_module.reload_filter_words()


@func_case
async def test_webui_policy(tester: Tester):
    """bots.web.api.policy: URL 审计名单与过滤词库接口测试"""
    await tester.test(_url_audit_case, "URL 审计名单接口读写、版本号与错误码")
    await tester.test(_filter_words_case, "过滤词库接口读写与即时重载")

    return tester
