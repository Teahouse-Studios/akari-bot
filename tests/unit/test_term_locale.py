"""术语占位符与会话术语作用域单元测试。"""

import ast
import json
from pathlib import Path

from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import _filter_message_chain_badwords
from core.builtins.session.terms import build_term_candidates
from core.i18n import Locale, audit_terms
from core.logger import Logger
from core.tester import func_case, Tester

# 该键的文案为「查看当前{TERM:target}的消息通道。」
TERM_DOC_KEY = "core.help.bind.channel"

EXPECTED_CANDIDATES = (
    ("QQ|Group", False, ("qq.group", "qq")),
    ("QQ|Private", True, ("qq.private", "private", "qq")),
    ("Discord|Channel", False, ("discord.channel", "discord")),
    ("Discord|DM|Channel", True, ("discord.dm.channel", "discord.dm", "private", "discord")),
    ("Discord|Guild", False, ("discord.guild", "discord")),
    ("Web|Console", True, ("web.console", "private", "web")),
    ("Matrix|Room", False, ("matrix.room", "matrix")),
    ("TEST|Console", False, ("test.console", "test")),
    (None, False, ()),
)

EXPECTED_WORDING = (
    ("QQ|Group", False, "群聊"),
    ("QQ|Private", True, "私聊"),
    ("Discord|Channel", False, "频道"),
    ("Discord|DM|Channel", True, "私聊"),
    ("Discord|Guild", False, "服务器"),
    ("QQBot|Group", False, "群聊"),
    ("QQBot|Guild", False, "频道"),
    ("QQBot|C2C", True, "私聊"),
    ("KOOK|Group", False, "频道"),
    ("KOOK|Person", True, "私聊"),
    ("Telegram|Group", False, "群组"),
    ("Telegram|Supergroup", False, "超级群组"),
    ("Telegram|Channel", False, "频道"),
    ("Telegram|Private", True, "私聊"),
    ("Matrix|Room", False, "聊天室"),
    ("Web|Console", True, "控制台"),
    ("TEST|Console", False, "场景"),
)

# 无会话上下文的 Locale 构造点：这些出口渲染的不是会话文案，或另有语言来源。
NON_SESSION_LOCALE_FILES = {
    "core/config/__init__.py": "配置模板注释",
    "core/config/update.py": "配置注释补写",
    "core/queue/server.py": "WebUI 帮助文档",
    "core/scripts/config_generate.py": "配置模板生成",
    "core/smtp.py": "邮件上报",
    "modules/core/admin_tools/locale.py": "语言名与翻译进度",
    "modules/weekly/__init__.py": "双语言周刊推送",
    "modules/weekly_rss/__init__.py": "双语言周刊推送",
    "modules/wiki/utils/screenshot_image.py": "wiki 差异渲染语言",
    "modules/wiki/utils/wikilib.py": "wiki 内容语言",
}

# 会话缺席时的兜底构造：此时本就没有作用域可言。
FALLBACK_LOCALE_SNIPPETS = {
    "core/builtins/message/chain.py": ("Locale(default_locale)",),
    "core/builtins/parser/command.py": ("Locale(default_locale)",),
    "core/builtins/session/info.py": ("field(factory=lambda: Locale(default_locale))",),
    "core/builtins/session/internal.py": ("Locale(default_locale)",),
}


def _wording(target_from: str | None, is_private: bool, locale: str = "zh_cn") -> str:
    scoped = Locale(locale, term_candidates=build_term_candidates(target_from, is_private))
    return scoped.t(TERM_DOC_KEY)


def _test_candidate_chain_building():
    for target_from, is_private, expected in EXPECTED_CANDIDATES:
        if build_term_candidates(target_from, is_private) != expected:
            return False
    # 前缀形状由平台侧决定：非法字符被剔除，剔除后为空的整条链回落到基础术语而非中断。
    if build_term_candidates("Bad.Prefix|X", False) != ("badprefix.x", "badprefix"):
        return False
    if build_term_candidates("QQ||Group", False) != ():
        return False
    return True


def _test_platform_wording():
    for target_from, is_private, expected in EXPECTED_WORDING:
        if _wording(target_from, is_private) != f"查看当前{expected}的消息通道。":
            return False
    return True


def _test_unscoped_locale_falls_back():
    unscoped = Locale("zh_cn")
    return (
        unscoped.term_scoped is False
        and unscoped.term_candidates is None
        and unscoped.t(TERM_DOC_KEY) == "查看当前场景的消息通道。"
    )


def _test_term_resolves_in_raw_text():
    scoped = Locale("zh_cn", term_candidates=build_term_candidates("QQ|Group", False))
    return (
        scoped.t_str("{TERM:target}") == "群聊"
        and scoped.t_str("{I18N:core.message.setup.list.target}") == "【群聊设置】"
        and scoped.t_str("{TERM:target} / {I18N:i18n.unit.1}") == "群聊 / 万"
        # 术语缺失时原样保留占位符，不抛错
        and scoped.t_str("{TERM:no_such_term}") == "{TERM:no_such_term}"
    )


def _test_with_locale_keeps_scope():
    scoped = Locale("zh_cn", term_candidates=build_term_candidates("Discord|Channel", False))
    derived = scoped.with_locale("zh_tw")
    return derived.term_scoped is True and derived.term_candidates == ("discord.channel", "discord")


async def _test_scope_survives_serialization():
    session_info = await SessionInfo.assign(
        target_id="QQ|Group|term", target_from="QQ|Group", client_name="QQ", create=True
    )
    raw = converter.unstructure(session_info)
    restored = converter.structure(raw, SessionInfo)
    restored_locale = restored.locale
    return (
        raw["locale"]["term_candidates"] == ["qq.group", "qq"]
        and restored_locale.term_scoped is True
        and restored_locale.t(TERM_DOC_KEY) == "查看当前群聊的消息通道。"
    )


async def _test_server_side_render_keeps_terms():
    session_info = await SessionInfo.assign(
        target_id="QQ|Group|term", target_from="QQ|Group", client_name="QQ", create=True
    )
    chain = MessageChain.assign(PlainElement.assign("本{TERM:target}已开启。"))
    rendered = _filter_message_chain_badwords(chain, session_info)
    return rendered.values[0].text == "本群聊已开启。"


async def _test_derive_private_session_refreshes_terms():
    session_info = await SessionInfo.assign(
        target_id="QQ|Group|term", target_from="QQ|Group", client_name="QQ", create=True
    )
    private_session = ContextManager.derive_private_session(session_info, "QQ|Private|9", "QQ|Private")
    return (
        private_session.is_private is True
        and private_session.locale.term_candidates == ("qq.private", "private", "qq")
        and private_session.locale.t(TERM_DOC_KEY) == "查看当前私聊的消息通道。"
    )


def _test_locale_files_pass_term_audit():
    errors = audit_terms()
    if errors:
        Logger.error(f"术语审计失败：{errors}")
    return not errors


def _test_term_keys_live_in_terms_directory():
    """术语词条只应出现在 `locales/terms/` 下；顶层残留副本会被术语目录覆盖并报审计条目。"""
    root = Path(__file__).resolve().parents[2]
    offenders = []
    patterns = ("core/locales/*.json", "bots/*/locales/*.json", "modules/*/locales/*.json")
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            data = json.loads(path.read_text(encoding="utf-8"))
            stale = [key for key in data if key.startswith("term.")]
            if stale:
                offenders.append(f"{path.relative_to(root).as_posix()}: {stale}")
    if offenders:
        Logger.error("术语词条应移入同目录的 terms/ 子目录：\n" + "\n".join(offenders))
    return not offenders


def _test_terms_directory_is_loaded():
    """术语目录里的键省略 `term.` 前缀，加载时按语言标签取文件。"""
    root = Path(__file__).resolve().parents[2]
    core_terms = json.loads((root / "core/locales/terms/zh_cn.json").read_text(encoding="utf-8"))
    if any(key.startswith("term.") for key in core_terms):
        return False
    scoped = Locale("zh_cn", term_candidates=build_term_candidates("Discord|Channel", False))
    return scoped.term_key("target") == "term.target.discord"


def _test_terms_vocabulary_is_centralized():
    """平台称呼差异集中在 core 的词表：术语词条是词表而非平台逻辑，单一归属也避免共用身份的键冲突。"""
    root = Path(__file__).resolve().parents[2]
    scattered = [path.relative_to(root).as_posix() for path in sorted(root.glob("bots/*/locales/terms"))]
    if scattered:
        Logger.error("适配器的术语词条应集中到 core/locales/terms/，当前存在于：" + ", ".join(scattered))
        return False
    return (root / "core/locales/terms/zh_cn.json").is_file()


def _scan_unscoped_locale_sites() -> list[str]:
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for base in ("core", "modules"):
        for path in sorted((root / base).rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative in NON_SESSION_LOCALE_FILES:
                continue
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines()
            snippets = FALLBACK_LOCALE_SNIPPETS.get(relative, ())
            # 按语法树而非物理行判定，避免多行调用与注释里的字样造成误报。
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "Locale":
                    continue
                if any(keyword.arg == "term_candidates" for keyword in node.keywords):
                    continue
                line = lines[node.lineno - 1]
                if any(snippet in line for snippet in snippets):
                    continue
                offenders.append(f"{relative}:{node.lineno}: {line.strip()}")
    return offenders


def _test_no_unscoped_locale_sites():
    offenders = _scan_unscoped_locale_sites()
    if offenders:
        Logger.error(
            "以下 Locale 构造点会丢掉术语作用域，请改用 term_candidates= 或 with_locale()：\n" + "\n".join(offenders)
        )
    return not offenders


@func_case
async def test_term_locale(tester: Tester):
    """core.i18n: 术语占位符与会话作用域测试"""
    await tester.test(_test_candidate_chain_building, "候选链构造测试")
    await tester.test(_test_platform_wording, "各平台术语文案测试")
    await tester.test(_test_unscoped_locale_falls_back, "未绑定作用域回落测试")
    await tester.test(_test_term_resolves_in_raw_text, "文本内术语解析测试")
    await tester.test(_test_with_locale_keeps_scope, "换语言保留作用域测试")
    await tester.test(_test_scope_survives_serialization, "会话序列化保留作用域测试")
    await tester.test(_test_server_side_render_keeps_terms, "出站渲染保留术语测试")
    await tester.test(_test_derive_private_session_refreshes_terms, "派生私聊会话刷新术语测试")
    await tester.test(_test_locale_files_pass_term_audit, "语言文件术语审计测试")
    await tester.test(_test_term_keys_live_in_terms_directory, "术语词条目录归属测试")
    await tester.test(_test_terms_directory_is_loaded, "术语目录加载测试")
    await tester.test(_test_terms_vocabulary_is_centralized, "术语词表集中归属测试")
    await tester.test(_test_no_unscoped_locale_sites, "Locale 构造点检查")

    return tester
