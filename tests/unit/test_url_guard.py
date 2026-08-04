"""未认证链接的呈现方式单元测试。

enable_urlmanager 开启时，未经认证的链接原本一律转为 ROT13 编码的跳板地址。跳板地址
无从辨识且须经第三方页面中转，故在支持 markdown 的会话上改以代码块呈现原始链接，供用户
自行复制，同时保留未认证的警示；不支持 markdown 的会话（含用户自行关闭 markdown 者）
仍走跳板。

易错处有二：其一是取链接须用 original_url——模块显式传入 trusted=False 时 url 字段已被
替换成跳板地址；其二是代码块内不可再套 [名称](URL)，故该路径须跳过 markdown 格式转换。
"""

from unittest.mock import patch

from attr import evolve

import bots.qqbot.features as qqbot_features_module
from bots.qqbot.features import features as qqbot_features
from bots.qqbot.features import resolve_features
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Url
from core.builtins.session.info import SessionInfo
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester

# 跳板服务的域名，用以断言某条路径确实未走跳板
_MM_HOST = "mm.teahouse.team"
_URL = "https://example.com/wiki/Page"


def _session(**kwargs) -> SessionInfo:
    """构造一个用于考察 URL 呈现的会话。

    :param kwargs: 覆盖到 SessionInfo 上的能力字段。
    :return: 会话信息。
    """
    return SessionInfo(
        target_id="QQBot|Group|url_guard",
        sender_id="QQBot|1",
        target_from="QQBot|Group",
        client_name="QQBot",
        session_id="url-guard",
        **kwargs,
    )


def _render(session_info: SessionInfo, trusted: bool | None = None, disable_markdown: bool = False) -> str:
    """跑一遍消息链转换，取回最终文本。

    :param session_info: 会话信息。
    :param trusted: 传给 Url 的认证标记；None 表示不表态，交由会话决定。
    :param disable_markdown: 是否在转换时强制禁用 markdown。
    :return: 转换后各元素拼接成的文本。
    """
    chain = MessageChain.assign([Url(_URL, trusted=trusted)])
    return "".join(str(x) for x in chain.as_sendable(session_info, disable_markdown=disable_markdown))


def _expected_block(session_info: SessionInfo) -> str:
    """按会话语言拼出预期的代码块，避免把文案写死在断言里。

    :param session_info: 会话信息。
    :return: 预期的代码块文本。
    """
    return f"```{session_info.locale.t('message.url.untrusted')}\n{_URL}\n```"


async def _test_markdown_session_gets_code_block():
    """测试代码块呈现 - 支持 markdown 时给出代码块，且不经跳板"""
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
    """测试三态 - 显式标记为不可信者一律保护，纵使会话未启用 URLManager

    wikilib 在内容审查未通过时即以 trusted=False 传入，该场景须无视会话设置。
    此路径下 url 字段已被替换成跳板地址，须取 original_url 方能拿回原链接。
    """
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
    """测试三态 - 已认证的链接不受保护，纵使会话启用了 URLManager"""
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True), trusted=True)
        if out != _URL:
            Logger.error(f"trusted url should be left untouched, got: {out!r}")
            return False
        return True

    except Exception:
        return False


async def _test_trusted_url_skips_springboard_without_markdown():
    """测试三态 - 已认证的链接在不支持 markdown 的会话上也不套跳板"""
    try:
        out = _render(_session(use_url_manager=True, support_markdown=False), trusted=True)
        return out == _URL and _MM_HOST not in out

    except Exception:
        return False


async def _test_md_format_not_applied_inside_code_block():
    """测试代码块呈现 - 代码块内不得再套 [名称](URL)"""
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True, use_url_md_format=True))
        return "](" not in out

    except Exception:
        return False


async def _test_markdown_off_falls_back_to_springboard():
    """测试回退 - 不支持 markdown 的会话仍走跳板"""
    try:
        out = _render(_session(use_url_manager=True, support_markdown=False))
        return _MM_HOST in out and not out.startswith("```")

    except Exception:
        return False


async def _test_disable_markdown_falls_back_to_springboard():
    """测试回退 - 转换时强制禁用 markdown 者同样走跳板"""
    try:
        out = _render(_session(use_url_manager=True, support_markdown=True), disable_markdown=True)
        return _MM_HOST in out and not out.startswith("```")

    except Exception:
        return False


async def _test_manager_off_leaves_url_untouched():
    """测试无关会话 - 未启用 URLManager 者链接原样输出"""
    try:
        return _render(_session(use_url_manager=False, support_markdown=True)) == _URL

    except Exception:
        return False


async def _test_qqbot_declares_url_manager():
    """测试平台接入 - qqbot 的能力集须跟随 enable_urlmanager

    此项此前未设置而取默认的 False，未认证链接在 qqbot 上因此从未被标记。
    """
    try:
        return qqbot_features.use_url_manager == CoreConfig.enable_urlmanager

    except Exception:
        return False


async def _test_markdown_toggle_keeps_url_manager():
    """测试平台接入 - 用户关闭 markdown 后仍须保留 URLManager

    关闭 markdown 只应令呈现退回跳板；若连 use_url_manager 一并关闭，未认证链接便
    完全不再被标记，等同于取消保护。
    """
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
    """测试 KE 码往返 - 认证标记须原样保留

    I18N 参数中的 MessageChain 会被转成 KE 码再解析回来（chain.py:340）。标记若在
    这一趟丢失，已认证的链接会退化为未表态，进而被会话的 URLManager 套上跳板。
    """
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
    """测试 KE 码往返 - 已套跳板者不得再套一层

    trusted 为 False 时 url 字段已是跳板地址，故 kecode 须编码 original_url；
    若照搬 url，还原时会在跳板地址之上再套一层跳板。
    """
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
    """测试 KE 码往返 - 未表态者往返后仍随会话而定"""
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
    await tester.test(_test_disable_markdown_falls_back_to_springboard, "强制禁用 markdown 时回退跳板测试")
    await tester.test(_test_manager_off_leaves_url_untouched, "未启用 URLManager 时原样输出测试")
    await tester.test(_test_trusted_survives_kecode_roundtrip, "认证标记经 KE 码往返保留测试")
    await tester.test(_test_untrusted_not_double_wrapped_by_kecode, "KE 码往返不重复套跳板测试")
    await tester.test(_test_unmarked_url_still_follows_session_after_roundtrip, "未表态者往返后随会话测试")
    await tester.test(_test_qqbot_declares_url_manager, "qqbot 接入 URLManager 测试")
    await tester.test(_test_markdown_toggle_keeps_url_manager, "关闭 markdown 保留 URLManager 测试")

    return tester
