"""未认证链接的呈现方式单元测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from attr import evolve

import bots.qqbot.features as qqbot_features_module
from bots.qqbot.features import features as qqbot_features
from bots.qqbot.features import resolve_features
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import EmbedElement
from core.builtins.message.internal import Embed, EmbedField, Url
from core.builtins.session.info import SessionInfo
from core.database.models import SenderUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester
from core.utils.url_audit import GlobalURLAllowlist, GlobalURLBlocklist

# 跳板服务的域名，用以断言某条路径确实未走跳板
_MM_HOST = "mm.teahouse.team"
_URL = "https://example.com/wiki/Page"


def _session(**kwargs) -> SessionInfo:
    return SessionInfo(
        target_id="QQBot|Group|url_guard",
        sender_id="QQBot|1",
        target_from="QQBot|Group",
        client_name="QQBot",
        session_id="url-guard",
        **kwargs,
    )


def _render(session_info: SessionInfo, trusted: bool | None = None, enable_markdown: bool = True) -> str:
    chain = MessageChain.assign([Url(_URL, trusted=trusted)])
    return "".join(str(x) for x in chain.as_sendable(session_info, enable_markdown=enable_markdown))


def _expected_block(session_info: SessionInfo) -> str:
    return f"```{session_info.locale.t('message.url.untrusted')}\n{_URL}\n```"


async def _test_markdown_session_gets_code_block():
    try:
        session_info = _session(use_url_manager=True, support_markdown=True, use_url_md_format=True)
        out = _render(session_info)
        if out != _expected_block(session_info):
            Logger.error(f"unexpected output for markdown session: {out!r}")
            return False
        return _MM_HOST not in out

    except Exception:
        return False


async def _test_explicit_untrusted_is_guarded():
    try:
        session_info = _session(use_url_manager=False, support_markdown=True)
        out = _render(session_info, trusted=False)
        if out != _expected_block(session_info):
            Logger.error(f"unexpected output for explicit untrusted url: {out!r}")
            return False
        return True

    except Exception:
        return False


async def _test_trusted_url_is_never_guarded():
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True), trusted=True)
        if out != _URL:
            Logger.error(f"trusted url should be left untouched, got: {out!r}")
            return False
        return True

    except Exception:
        return False


async def _test_trusted_url_skips_springboard_without_markdown():
    try:
        out = _render(_session(use_url_manager=True, support_markdown=False), trusted=True)
        return out == _URL and _MM_HOST not in out

    except Exception:
        return False


async def _test_md_format_not_applied_inside_code_block():
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True, use_url_md_format=True))
        return "](" not in out

    except Exception:
        return False


async def _test_markdown_off_falls_back_to_springboard():
    try:
        out = _render(_session(use_url_manager=True, support_markdown=False))
        return _MM_HOST in out and not out.startswith("```")

    except Exception:
        return False


async def _test_enable_markdown_falls_back_to_springboard():
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True), enable_markdown=False)
        return _MM_HOST in out and not out.startswith("```")

    except Exception:
        return False


async def _test_manager_off_leaves_url_untouched():
    try:
        return _render(_session(use_url_manager=False, support_markdown=True)) == _URL

    except Exception:
        return False


async def _test_global_allowlist_bypasses_guard():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLAllowlist, "directory", directory),
                patch.object(GlobalURLAllowlist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLAllowlist, "user_path", directory / "user.txt"),
            ):
                GlobalURLAllowlist.clear_cache()
                GlobalURLAllowlist.add_user_rule(_URL)
                out = _render(_session(use_url_manager=True, support_markdown=True))
                return out == _URL
    except Exception:
        return False
    finally:
        GlobalURLAllowlist.clear_cache()


async def _test_explicit_untrusted_overrides_global_allowlist():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLAllowlist, "directory", directory),
                patch.object(GlobalURLAllowlist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLAllowlist, "user_path", directory / "user.txt"),
            ):
                GlobalURLAllowlist.clear_cache()
                GlobalURLAllowlist.add_user_rule(_URL)
                session_info = _session(use_url_manager=True, support_markdown=True)
                return _render(session_info, trusted=False) == _expected_block(session_info)
    except Exception:
        return False
    finally:
        GlobalURLAllowlist.clear_cache()


async def _test_global_blocklist_blocks_trusted_url():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLBlocklist, "directory", directory),
                patch.object(GlobalURLBlocklist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLBlocklist, "user_path", directory / "user.txt"),
            ):
                GlobalURLBlocklist.clear_cache()
                GlobalURLBlocklist.add_user_rule(_URL)
                session_info = _session(use_url_manager=False, support_markdown=True)
                out = _render(session_info, trusted=True)
                return out == session_info.locale.t("message.url.blocked") and _URL not in out
    except Exception:
        return False
    finally:
        GlobalURLBlocklist.clear_cache()


async def _test_global_blocklist_overrides_allowlist():
    try:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            allowlist_directory = root / "allowlist"
            blocklist_directory = root / "blocklist"
            with (
                patch.object(GlobalURLAllowlist, "directory", allowlist_directory),
                patch.object(GlobalURLAllowlist, "builtin_path", allowlist_directory / "global.txt"),
                patch.object(GlobalURLAllowlist, "user_path", allowlist_directory / "user.txt"),
                patch.object(GlobalURLBlocklist, "directory", blocklist_directory),
                patch.object(GlobalURLBlocklist, "builtin_path", blocklist_directory / "global.txt"),
                patch.object(GlobalURLBlocklist, "user_path", blocklist_directory / "user.txt"),
            ):
                GlobalURLAllowlist.clear_cache()
                GlobalURLBlocklist.clear_cache()
                GlobalURLAllowlist.add_user_rule(_URL)
                GlobalURLBlocklist.add_user_rule(_URL)
                session_info = _session(use_url_manager=True, support_markdown=True)
                out = _render(session_info)
                return out == session_info.locale.t("message.url.blocked") and _URL not in out
    except Exception:
        return False
    finally:
        GlobalURLAllowlist.clear_cache()
        GlobalURLBlocklist.clear_cache()


async def _test_global_blocklist_removes_embed_url():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLBlocklist, "directory", directory),
                patch.object(GlobalURLBlocklist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLBlocklist, "user_path", directory / "user.txt"),
            ):
                GlobalURLBlocklist.clear_cache()
                GlobalURLBlocklist.add_user_rule(_URL)
                session_info = _session(support_embed=True)
                out = MessageChain.assign(
                    [
                        Embed(
                            title="Blocked",
                            description=f"before {_URL} after",
                            url=_URL,
                            fields=[EmbedField("link", _URL)],
                        )
                    ]
                ).as_sendable(session_info)
                embed = out.values[0] if len(out.values) == 1 and isinstance(out.values[0], EmbedElement) else None
                return (
                    embed is not None
                    and embed.url is None
                    and _URL not in embed.description
                    and _URL not in embed.fields[0].value
                )
    except Exception:
        return False
    finally:
        GlobalURLBlocklist.clear_cache()


async def _test_global_blocklist_redacts_plain_text_url():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLBlocklist, "directory", directory),
                patch.object(GlobalURLBlocklist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLBlocklist, "user_path", directory / "user.txt"),
            ):
                GlobalURLBlocklist.clear_cache()
                GlobalURLBlocklist.add_user_rule(_URL)
                session_info = _session()
                out = "".join(str(x) for x in MessageChain.assign(f"before {_URL}, after").as_sendable(session_info))
                return out == f"before {session_info.locale.t('message.url.blocked')}, after" and _URL not in out
    except Exception:
        return False
    finally:
        GlobalURLBlocklist.clear_cache()


async def _test_global_blocklist_fails_closed_on_regex_budget_exhaustion():
    try:
        with TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            with (
                patch.object(GlobalURLBlocklist, "directory", directory),
                patch.object(GlobalURLBlocklist, "builtin_path", directory / "global.txt"),
                patch.object(GlobalURLBlocklist, "user_path", directory / "user.txt"),
            ):
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "global.txt").write_text(
                    r"regex:https://blocked\.example\.test/.*" + "\n", encoding="utf-8"
                )
                GlobalURLBlocklist.clear_cache()
                with patch("core.utils.url_audit.time.monotonic", side_effect=[0.0, 1.0]):
                    return GlobalURLBlocklist.is_blocked(_URL)
    except Exception:
        return False
    finally:
        GlobalURLBlocklist.clear_cache()


async def _test_markdown_toggle_keeps_url_manager():
    try:
        # 平台能力集在导入时即依配置定型，故另建一份「markdown 与 URLManager 均已开启」
        # 的基准并打桩该开关，使断言只考察覆盖逻辑本身，不受本地配置左右
        session_info = _session(
            sender_union_info=SenderUnionInfo(union_id="USID|1", sender_data={"use_markdown": False})
        )
        base = evolve(qqbot_features, support_markdown=True, use_url_manager=True)
        with patch.object(qqbot_features_module, "qq_use_markdown", True):
            resolved = resolve_features(session_info, base)
        if resolved.support_markdown is not False:
            Logger.error("support_markdown should be turned off when the user disables markdown")
            return False
        if resolved.use_url_manager is not True:
            Logger.error("use_url_manager must survive the markdown toggle")
            return False
        return True

    except Exception:
        return False


async def _test_trusted_survives_kecode_roundtrip():
    try:
        session_info = _session(use_url_manager=True, support_markdown=False)
        code = MessageChain.assign([Url(_URL, trusted=True)]).to_kecode()
        out = "".join(str(x) for x in MessageChain.assign(code).as_sendable(session_info))
        if out != _URL:
            Logger.error(f"trusted lost across kecode roundtrip: {out!r}")
            return False
        return True

    except Exception:
        return False


async def _test_untrusted_not_double_wrapped_by_kecode():
    try:
        session_info = _session(use_url_manager=True, support_markdown=False)
        code = MessageChain.assign([Url(_URL, trusted=False)]).to_kecode()
        out = "".join(str(x) for x in MessageChain.assign(code).as_sendable(session_info))
        expected = str(Url(_URL, trusted=False))
        if out != expected:
            Logger.error(f"springboard applied twice across kecode roundtrip: {out!r}")
            return False
        return True

    except Exception:
        return False


async def _test_unmarked_url_still_follows_session_after_roundtrip():
    try:
        session_info = _session(use_url_manager=True, support_markdown=False)
        code = MessageChain.assign([Url(_URL)]).to_kecode()
        out = "".join(str(x) for x in MessageChain.assign(code).as_sendable(session_info))
        return _MM_HOST in out

    except Exception:
        return False


@func_case
async def test_url_guard(tester: Tester):
    """未认证链接：代码块呈现与回退测试"""
    await tester.test(_test_markdown_session_gets_code_block, "支持 markdown 时给出代码块测试")
    await tester.test(_test_explicit_untrusted_is_guarded, "显式不可信者走代码块测试")
    await tester.test(_test_trusted_url_is_never_guarded, "已认证链接不受保护测试")
    await tester.test(_test_trusted_url_skips_springboard_without_markdown, "已认证链接不套跳板测试")
    await tester.test(_test_md_format_not_applied_inside_code_block, "代码块内不套链接格式测试")
    await tester.test(_test_markdown_off_falls_back_to_springboard, "不支持 markdown 时回退跳板测试")
    await tester.test(_test_enable_markdown_falls_back_to_springboard, "强制禁用 markdown 时回退跳板测试")
    await tester.test(_test_manager_off_leaves_url_untouched, "未启用 URLManager 时原样输出测试")
    await tester.test(_test_global_allowlist_bypasses_guard, "全局 URL 允许列表放行测试")
    await tester.test(_test_explicit_untrusted_overrides_global_allowlist, "显式不可信优先级测试")
    await tester.test(_test_global_blocklist_blocks_trusted_url, "全局 URL 阻止列表覆盖可信标记测试")
    await tester.test(_test_global_blocklist_overrides_allowlist, "全局 URL 阻止列表覆盖允许列表测试")
    await tester.test(_test_global_blocklist_removes_embed_url, "全局 URL 阻止列表移除 Embed 链接测试")
    await tester.test(_test_global_blocklist_redacts_plain_text_url, "全局 URL 阻止列表过滤纯文本链接测试")
    await tester.test(
        _test_global_blocklist_fails_closed_on_regex_budget_exhaustion,
        "全局 URL 阻止列表正则预算耗尽时拒绝发送测试",
    )
    await tester.test(_test_trusted_survives_kecode_roundtrip, "认证标记经 KE 码往返保留测试")
    await tester.test(_test_untrusted_not_double_wrapped_by_kecode, "KE 码往返不重复套跳板测试")
    await tester.test(_test_unmarked_url_still_follows_session_after_roundtrip, "未表态者往返后随会话测试")
    await tester.test(_test_markdown_toggle_keeps_url_manager, "关闭 markdown 保留 URLManager 测试")

    return tester
