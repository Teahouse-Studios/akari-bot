"""未认证链接的呈现方式单元测试。

enable_urlmanager 开启时，未经认证的链接原本一律转为 ROT13 编码的跳板地址。跳板地址
无从辨识且须经第三方页面中转，故在支持 markdown 的会话上改以代码块呈现原始链接，供用户
自行复制，同时保留未认证的警示；不支持 markdown 的会话（含用户自行关闭 markdown 者）
仍走跳板。

易错处有二：其一是取链接须用 original_url——模块显式传入 use_mm=True 时 url 字段已被
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


def _render(session_info: SessionInfo, use_mm: bool | None = None, disable_markdown: bool = False) -> str:
    """跑一遍消息链转换，取回最终文本。

    :param session_info: 会话信息。
    :param use_mm: 传给 Url 的跳板开关；None 表示交由会话决定。
    :param disable_markdown: 是否在转换时强制禁用 markdown。
    :return: 转换后各元素拼接成的文本。
    """
    chain = MessageChain.assign([Url(_URL, use_mm=use_mm)])
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


async def _test_explicit_use_mm_also_guarded():
    """测试代码块呈现 - 模块显式要求跳板的链接同样改以代码块呈现

    modules/wiki 多处以 use_mm=... 显式传入。该路径下 applied_mm 已为真、url 已被替换
    成跳板地址，须取 original_url 方能拿回原链接。
    """
    try:
        session_info = _session(use_url_manager=False, support_markdown=True)
        out = _render(session_info, use_mm=True)
        if out != _expected_block(session_info):
            Logger.error(f"unexpected output for explicit use_mm: {out!r}")
            return False
        return True

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


@func_case
async def test_url_guard(tester: Tester):
    """未认证链接：代码块呈现与回退测试"""
    await tester.test(_test_markdown_session_gets_code_block, "支持 markdown 时给出代码块测试")
    await tester.test(_test_explicit_use_mm_also_guarded, "显式要求跳板者同样走代码块测试")
    await tester.test(_test_md_format_not_applied_inside_code_block, "代码块内不套链接格式测试")
    await tester.test(_test_markdown_off_falls_back_to_springboard, "不支持 markdown 时回退跳板测试")
    await tester.test(_test_disable_markdown_falls_back_to_springboard, "强制禁用 markdown 时回退跳板测试")
    await tester.test(_test_manager_off_leaves_url_untouched, "未启用 URLManager 时原样输出测试")
    await tester.test(_test_qqbot_declares_url_manager, "qqbot 接入 URLManager 测试")
    await tester.test(_test_markdown_toggle_keeps_url_manager, "关闭 markdown 保留 URLManager 测试")

    return tester
