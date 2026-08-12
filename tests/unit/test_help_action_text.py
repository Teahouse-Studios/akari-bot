"""帮助页布局与可点击模块列表的单元测试。

`~help` 与 `~module list` 列出的模块名，在具备指令操作能力的平台上做成可点击标签，
点击即把 `~help <模块名>` 填入输入框。此处把关三件事：元素序列的交错排布、标题
末尾的换行，以及经适配器渲染后的分行结果。

标题的换行是易错点：适配器会把指令操作无条件拼入上一项，标题若不自带换行，
模块列表会被挤到标题同一行，与既有的纯文本版排版不符。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, ButtonFrameElement, ImageElement, PlainElement
from core.builtins.message.internal import ActionText, I18NContext, Image, Plain
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.constants.exceptions import SessionFinished
from core.i18n import Locale
from core.logger import Logger
from core.tester import func_case, Tester
from core.utils.table import TABLE_MAX_ROWS, format_table_code
from modules.core.help import (
    ModuleListEntry,
    build_clickable_modules,
    build_command_table,
    build_module_table,
    end_inline_run,
    env,
    get_module_type_display,
    get_help_link_buttons,
    help_overview,
    modules_list_help,
    strip_command_arguments,
)

# 表格测试所用的表头键，此处不校验其内容，只借它走通渲染
TABLE_TITLE_KEY = "core.message.help.table.title"


def _test_help_about_button_replaces_donate():
    msg = SimpleNamespace(session_info=SimpleNamespace(support_button=True, locale=Locale("zh_cn")))
    with patch("modules.core.help.help_url", "https://example.com/docs"):
        buttons = get_help_link_buttons(msg, include_modules=False)
    return buttons == [("📃 在线文档", "https://example.com/docs"), ("ℹ️ 关于我们", "~about")]


def _render_lines(session_info, parts) -> list[str]:
    """把元素列表按适配器的规则折成行。

    复刻 ``bots/qqbot/context.py`` 中 send_msg_markdown() 的拼接：指令操作并入上一项，
    且其后紧随的文本同样并入上一项，最后以换行连接各项。该函数绑在平台 SDK 上，
    测试无从直接调用，故按同样的规则建模。

    :param session_info: 会话信息，用于将消息链转为可发送形态。
    :param parts: 待折行的消息元素。
    :return: 折行后的文本行，不过滤空行。
    """
    texts, inline_pending = [], False
    for x in MessageChain.assign(parts).as_sendable(session_info).values:
        if isinstance(x, ButtonFrameElement):
            continue
        if isinstance(x, ActionTextElement):
            # show 为选填，缺省时平台取 text 展示
            tag = f"[{x.show.text if x.show else x.text.text}]"
            if texts:
                texts[-1] += tag
            else:
                texts.append(tag)
            inline_pending = True
        else:
            if inline_pending and texts:
                texts[-1] += x.text
            else:
                texts.append(x.text)
            inline_pending = False
    return "\n".join(texts).split("\n")


async def _session(target_suffix: str, support_action_text: bool = True):
    """构造一个用于消息链转换的会话。

    :param target_suffix: 场景 ID 后缀，各用例互不相同以免共用 union。
    :param support_action_text: 会话是否支持指令操作。
    :return: 会话信息。
    """
    return await SessionInfo.assign(
        target_id=f"TEST|Group|{target_suffix}",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(support_action_text=support_action_text),
    )


class _FakeSession:
    """只提供 build_clickable_modules 用到的两个属性。"""

    def __init__(self, session_info):
        self.session_info = session_info


class _ImageHelpSession(_FakeSession):
    def __init__(self, session_info, parsed_msg=None):
        super().__init__(session_info)
        self.parsed_msg = parsed_msg or {}
        self.finished_message = None

    async def finish(self, message, **kwargs):
        self.finished_message = MessageChain.assign(message)
        raise SessionFinished


class _OverviewSession(_ImageHelpSession):
    def __init__(self, session_info, is_admin: bool, is_superuser: bool = False):
        super().__init__(session_info)
        self.is_admin = is_admin
        self.is_superuser = is_superuser

    async def check_permission(self):
        return self.is_admin

    def check_super_user(self):
        return self.is_superuser

    async def finish(self, message, **kwargs):
        self.finished_message = MessageChain.assign(message)
        raise SessionFinished


def _button_rows(chain: MessageChain) -> list[dict[str, str]]:
    return [
        {button.show: button.value for button in row.buttons}
        for element in chain.values
        if isinstance(element, ButtonFrameElement)
        for row in element.rows
    ]


def _module(name: str, *, base: bool = False, rss: bool = False, unsupported: bool = False):
    return SimpleNamespace(
        module_name=name,
        base=base,
        rss=rss,
        hidden=False,
        _db_load=True,
        required_superuser=False,
        required_base_superuser=False,
        unsupported_reason=lambda _session_info: "rss" if unsupported else None,
    )


async def _test_image_help_precedes_action_text_fallback():
    """不支持 Markdown 表格时，即使支持 ActionText 也应优先生成图片帮助。"""
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|help_image_priority",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(
            support_image=True,
            support_action_text=True,
            support_markdown_table=False,
        ),
    )
    msg = _ImageHelpSession(session_info)
    generated = [Image("help.png")]
    try:
        with patch("modules.core.help.help_generator", new=AsyncMock(return_value=generated)) as generator:
            await modules_list_help(msg, legacy=False)
    except SessionFinished:
        pass
    sendable = msg.finished_message.as_sendable(session_info).values if msg.finished_message else []
    return (
        generator.await_count == 1
        and msg.finished_message is not None
        and any(isinstance(element, ImageElement) for element in msg.finished_message.values)
        and any(isinstance(element, ActionTextElement) and element.text.text == "~help " for element in sendable)
    )


async def _test_image_flag_overrides_markdown_table():
    """--image 应在支持 Markdown 表格的平台上仍强制生成图片帮助。"""
    session_info = await SessionInfo.assign(
        target_id="TEST|Group|help_force_image",
        target_from="TEST|Group",
        client_name="TEST",
        sender_id="TEST|1",
        features=Features(
            support_image=True,
            support_action_text=True,
            support_markdown_table=True,
        ),
    )
    msg = _ImageHelpSession(session_info, parsed_msg={"--image": True})
    generated = [Image("help.png")]
    try:
        with patch("modules.core.help.help_generator", new=AsyncMock(return_value=generated)) as generator:
            await help_overview(msg)
    except SessionFinished:
        pass
    sendable = msg.finished_message.as_sendable(session_info).values if msg.finished_message else []
    return (
        generator.await_count == 1
        and msg.finished_message is not None
        and any(isinstance(element, ImageElement) for element in msg.finished_message.values)
        and any(isinstance(element, ActionTextElement) and element.text.text == "~help " for element in sendable)
    )


async def _test_image_template_omits_help_command():
    """图片帮助页不内嵌查看详情命令，并以色块图例说明模块类型。"""
    locale = (await _session("help_image_template")).locale
    rendered = await env.get_template("module_list.html").render_async(
        msg=SimpleNamespace(session_info=SimpleNamespace(prefixes=["~"])),
        locale=locale,
        CommandParser=None,
        is_base_superuser=False,
        is_superuser=False,
        len=len,
        module_list={},
        module_groups=[],
        show_disabled_modules=True,
        target_enabled_list=[],
        use_font_mirror=False,
    )
    swatches = (
        "module-type-legend-base",
        "module-type-legend-external",
        "module-type-legend-subscription",
        "module-type-legend-disabled",
    )
    return (
        "${cmd}" not in rendered
        and "~help " not in rendered
        and "模块名称" not in rendered
        and all(swatch in rendered for swatch in swatches)
        and not any(color in rendered for color in ("橙色", "蓝色", "绿色", "灰色"))
    )


async def _test_help_doc_template_marks_module_type_with_swatch():
    """模块详细帮助使用色块与类型名称标识当前模块。"""
    locale = (await _session("help_doc_template")).locale
    module = SimpleNamespace(base=True, rss=False, desc="", alias={}, developers=[])
    help_ = SimpleNamespace(args={}, return_formatted_help_doc=lambda: "")
    rendered = await env.get_template("help_doc.html").render_async(
        locale=locale,
        module=module,
        help=help_,
        help_name="help",
        regex_list=[],
        escape=str,
        isinstance=isinstance,
        str=str,
        repattern=object,
        use_font_mirror=False,
    )
    return 'class="module-type-swatch"' in rendered and "基础模块" in rendered and "橙色" not in rendered


async def _test_markdown_help_marks_module_type_with_emoji():
    """Markdown 模块详情使用 emoji 色块与类型名称标识当前模块。"""
    locale = (await _session("help_markdown_type")).locale
    module_types = (
        (SimpleNamespace(base=True, rss=False), "🟧 基础模块"),
        (SimpleNamespace(base=False, rss=False), "🟦 扩展模块"),
        (SimpleNamespace(base=False, rss=True), "🟩 订阅扩展模块"),
    )
    return all(get_module_type_display(module, locale) == expected for module, expected in module_types)


async def _test_element_sequence():
    """测试标题、指令操作与分隔符的交错排布"""
    try:
        msg = _FakeSession(await _session("help_seq"))
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki", "maimai"])])
        kinds = [type(p).__name__ for p in parts]
        if kinds != ["PlainElement", "ActionTextElement", "PlainElement", "ActionTextElement"]:
            return False
        # 分隔符夹在两个标签之间
        if parts[2].text != " | ":
            return False
        return True
    except Exception:
        return False


async def _test_title_ends_with_newline():
    """测试标题自带换行

    适配器把指令操作无条件拼入上一项，标题不带换行会让列表挤到同一行。
    """
    try:
        msg = _FakeSession(await _session("help_nl"))
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki"])])
        title = parts[0]
        if not isinstance(title, PlainElement):
            return False
        if not title.text.endswith("\n"):
            return False
        # 换行之外的部分即该键的译文
        if title.text != msg.session_info.locale.t("core.message.help.legacy.base") + "\n":
            return False
        return True
    except Exception:
        return False


async def _test_action_text_payload():
    """测试标签的填入命令与展示文案"""
    try:
        session_info = await _session("help_payload")
        msg = _FakeSession(session_info)
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki"])])
        action = parts[1]
        if not isinstance(action, ActionTextElement):
            return False
        if action.text.text != f"{session_info.prefixes[0]}help wiki":
            return False
        if action.show.text != "wiki":
            return False
        return True
    except Exception:
        return False


async def _test_module_toggle_payloads():
    """测试普通与订阅模块的锁图标及 enable/disable 填入命令。"""
    session_info = await _session("help_toggle")
    msg = _FakeSession(session_info)
    prefix = session_info.prefixes[0]
    cases = (
        (ModuleListEntry("wiki", True), "🔓", f"{prefix}disable wiki"),
        (ModuleListEntry("dice", False), "🔐", f"{prefix}enable dice"),
        (ModuleListEntry("wikilog", True, subscription=True), "🔔", f"{prefix}disable wikilog"),
        (ModuleListEntry("weekly", False, subscription=True), "🔕", f"{prefix}enable weekly"),
    )
    for entry, emoji, command in cases:
        parts = build_clickable_modules(msg, [(TABLE_TITLE_KEY, [entry])])
        actions = [part for part in parts if isinstance(part, ActionTextElement)]
        if len(actions) != 2:
            return False
        if actions[0].show.text != emoji or actions[0].text.text != command:
            return False
        if actions[1].show.text != entry.name or actions[1].text.text != f"{prefix}help {entry.name}":
            return False
    return True


async def _test_unsupported_module_strikethrough():
    """测试缺少 QQBot 权限的模块以删除线展示，状态按钮仍可点击。"""
    session_info = await _session("help_strikethrough")
    msg = _FakeSession(session_info)
    entry = ModuleListEntry("wikilog", False, subscription=True, unsupported=True)
    lines = [
        line for line in _render_lines(session_info, build_module_table(msg, [(TABLE_TITLE_KEY, [entry])])) if line
    ]
    return any("~~[wikilog]~~" in line and "[🔕]" in line for line in lines)


async def _test_module_table_group_legends():
    """管理员模块表在扩展模块标题右侧展示开关图例，普通列表不展示。"""
    session_info = await _session("help_group_legends")
    msg = _FakeSession(session_info)
    groups = [
        ("core.message.help.table.external", [ModuleListEntry("wiki", True)]),
        ("core.message.help.table.subscription", [ModuleListEntry("wikilog", False, subscription=True)]),
    ]
    lines = [line for line in _render_lines(session_info, build_module_table(msg, groups)) if line]
    plain_lines = [
        line
        for line in _render_lines(
            session_info,
            build_module_table(msg, [("core.message.help.table.external", ["wiki"])]),
        )
        if line
    ]
    return (
        lines[0].startswith("| 扩展模块 | 🔓 = 已启用 | 🔐 = 已禁用 |")
        and any(line.startswith("| 订阅扩展模块 | 🔔 = 已启用 | 🔕 = 已禁用 |") for line in lines)
        and not any("已启用" in line or "已禁用" in line for line in plain_lines)
        and all(line.startswith("|") and line.endswith("|") for line in lines)
    )


async def _test_markdown_help_header():
    """测试 Markdown help 顶栏使用四个真实单元格，并与模块列表处于同一张表。"""
    session_info = await _session("help_header")
    session_info.bot_name = "小可测试版"
    msg = _FakeSession(session_info)
    try:
        with patch("modules.core.help.get_version_display", return_value="v1.2.3"):
            parts = build_module_table(
                msg,
                [(TABLE_TITLE_KEY, ["wiki", "dice", "coin"])],
                include_help_header=True,
                permission="admin",
            )
        actions = [part for part in parts if isinstance(part, ActionTextElement)]
        locale_actions = [action for action in actions if action.text.text == f"{session_info.prefixes[0]}locale"]
        version_actions = [action for action in actions if action.text.text == f"{session_info.prefixes[0]}version"]
        if len(locale_actions) != 1 or len(version_actions) != 1:
            return False
        sendable = MessageChain.assign(parts).as_sendable(session_info).values
        rendered = "".join(
            element.text if isinstance(element, PlainElement) else f"[{element.show.text}]" for element in sendable
        )
        lines = [line for line in rendered.splitlines() if line]
        return (
            lines[0] == "| 小可测试版 | [语言：简体中文] | [版本：v1.2.3] | 当前权限：场景管理员 |"
            and lines[1] == "|---|---|---|---|"
            and lines[2].startswith("| ")
            and lines[3] == "| [wiki] | [dice] | [coin] | |"
            and {line.count("|") for line in lines} == {5}
            and rendered.count("|---|---|---|---|") == 1
            and "\n\n" not in rendered
        )
    except Exception:
        return False


async def _test_markdown_help_header_permissions_and_width():
    """测试三种权限文案，并确保宽表顶栏使用空单元格补齐而非合并。"""
    session_info = await _session("help_header_permissions")
    msg = _FakeSession(session_info)
    names = [f"m{i}" for i in range(41)]
    expected_permissions = {
        "user": "当前权限：普通用户",
        "admin": "当前权限：场景管理员",
        "superuser": "当前权限：超级用户",
    }
    try:
        with patch("modules.core.help.get_version_display", return_value=None):
            for permission, display in expected_permissions.items():
                parts = build_module_table(
                    msg,
                    [(TABLE_TITLE_KEY, names)],
                    include_help_header=True,
                    permission=permission,
                )
                lines = [line for line in _render_lines(session_info, parts) if line]
                separator_width = lines[1].count("|")
                if display not in lines[0] or "版本：未知" not in lines[0]:
                    return False
                if any(line.count("|") != separator_width for line in lines):
                    return False
                if not lines[0].endswith("| |"):
                    return False
        return True
    except Exception:
        return False


async def _test_qqbot_admin_help_includes_disabled_modules():
    """测试 QQBot 管理员的 help 合并 module list，并移除模块列表按钮。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|help_admin",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(
            support_action_text=True,
            support_button=True,
            support_markdown=True,
            support_markdown_table=True,
            support_rss=True,
        ),
    )
    session_info.enabled_modules = ["dice"]
    msg = _OverviewSession(session_info, is_admin=True)
    modules = {
        "help": _module("help", base=True),
        "coin": _module("coin"),
        "dice": _module("dice"),
    }
    try:
        with patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules):
            await help_overview(msg)
    except SessionFinished:
        pass
    sendable = msg.finished_message.as_sendable(session_info).values
    commands = [element.text.text for element in sendable if isinstance(element, ActionTextElement)]
    rendered = "\n".join(_render_lines(session_info, msg.finished_message.values))
    buttons = {label: command for row in _button_rows(msg.finished_message) for label, command in row.items()}
    return (
        "~enable coin" in commands
        and "~disable dice" in commands
        and "~disable help" not in commands
        and "[help]" in rendered
        and "场景管理员" in rendered
        and not any(command.endswith("module list") for command in buttons.values())
    )


async def _test_qqbot_superuser_help_header():
    """测试超级用户权限高于场景管理员，顶栏显示最高权限。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|help_superuser",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(
            support_action_text=True,
            support_button=True,
            support_markdown=True,
            support_markdown_table=True,
        ),
    )
    msg = _OverviewSession(session_info, is_admin=True, is_superuser=True)
    modules = {"help": _module("help", base=True)}
    try:
        with patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules):
            await help_overview(msg)
    except SessionFinished:
        pass
    rendered = "\n".join(_render_lines(session_info, msg.finished_message.values))
    return "超级用户" in rendered and "场景管理员" not in rendered


async def _test_qqbot_non_admin_help_keeps_module_list_button():
    """测试 QQBot 非管理员的 help 只展示已开启模块，并保留 module list 按钮。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|help_member",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(
            support_action_text=True,
            support_button=True,
            support_markdown=True,
            support_markdown_table=True,
            support_rss=True,
        ),
    )
    session_info.enabled_modules = ["dice"]
    msg = _OverviewSession(session_info, is_admin=False)
    modules = {
        "help": _module("help", base=True),
        "coin": _module("coin"),
        "dice": _module("dice"),
    }
    try:
        with patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules):
            await help_overview(msg)
    except SessionFinished:
        pass
    rendered = "\n".join(_render_lines(session_info, msg.finished_message.values))
    buttons = {label: command for row in _button_rows(msg.finished_message) for label, command in row.items()}
    return (
        "[dice]" in rendered
        and "[coin]" not in rendered
        and "普通用户" in rendered
        and any(command.endswith("module list") for command in buttons.values())
    )


async def _test_qqbot_admin_legacy_help_keeps_legacy_scope():
    """测试显式 --legacy 仍只展示已开启模块，不启用管理合并样式。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|help_admin_legacy",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(support_button=True),
    )
    session_info.enabled_modules = ["dice"]
    msg = _OverviewSession(session_info, is_admin=True)
    msg.parsed_msg = {"--legacy": True}
    modules = {
        "help": _module("help", base=True),
        "coin": _module("coin"),
        "dice": _module("dice"),
    }
    try:
        with patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules):
            await help_overview(msg)
    except SessionFinished:
        pass
    rendered = msg.finished_message.to_str()
    buttons = {label: command for row in _button_rows(msg.finished_message) for label, command in row.items()}
    return (
        "dice" in rendered
        and "coin" not in rendered
        and any(command.endswith("module list") for command in buttons.values())
    )


async def _test_qqbot_module_list_hides_toggles_from_non_admin():
    """测试 QQBot 普通用户的 module list 隐藏开关，底部只保留在线文档按钮。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|module_list_member",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(
            support_action_text=True,
            support_button=True,
            support_markdown=True,
            support_markdown_table=True,
            support_rss=True,
        ),
    )
    session_info.enabled_modules = ["dice", "wikilog"]
    msg = _OverviewSession(session_info, is_admin=False)
    modules = {
        "coin": _module("coin"),
        "dice": _module("dice"),
        "wikilog": _module("wikilog", rss=True),
    }
    try:
        with (
            patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules),
            patch("modules.core.help.help_url", "https://example.com/help"),
        ):
            await modules_list_help(msg, legacy=False)
    except SessionFinished:
        pass
    sendable = msg.finished_message.as_sendable(session_info).values
    commands = [element.text.text for element in sendable if isinstance(element, ActionTextElement)]
    rendered = "\n".join(_render_lines(session_info, msg.finished_message.values))
    button_commands = [command for row in _button_rows(msg.finished_message) for command in row.values()]
    return (
        all(f"[{name}]" in rendered for name in modules)
        and not any(emoji in rendered for emoji in ("🔐", "🔓", "🔕", "🔔"))
        and not any(command.startswith(("~enable ", "~disable ")) for command in commands)
        and button_commands == ["~help --doc"]
    )


async def _test_qqbot_module_list_keeps_toggles_for_admin():
    """测试 QQBot 场景管理员的 module list 仍提供模块开关。"""
    session_info = await SessionInfo.assign(
        target_id="QQBot|Group|module_list_admin",
        target_from="QQBot|Group",
        client_name="QQBot",
        sender_id="QQBot|1",
        features=Features(
            support_action_text=True,
            support_markdown=True,
            support_markdown_table=True,
        ),
    )
    session_info.enabled_modules = ["dice"]
    msg = _OverviewSession(session_info, is_admin=True)
    modules = {
        "coin": _module("coin"),
        "dice": _module("dice"),
    }
    try:
        with patch("modules.core.help.ModulesManager.return_modules_list", return_value=modules):
            await modules_list_help(msg, legacy=False)
    except SessionFinished:
        pass
    sendable = msg.finished_message.as_sendable(session_info).values
    commands = [element.text.text for element in sendable if isinstance(element, ActionTextElement)]
    return "~enable coin" in commands and "~disable dice" in commands


async def _test_single_module_no_separator():
    """测试只有一个模块时不产出多余分隔符"""
    try:
        msg = _FakeSession(await _session("help_single"))
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki"])])
        if len(parts) != 2:
            return False
        if any(isinstance(p, PlainElement) and p.text == " | " for p in parts[1:]):
            return False
        return True
    except Exception:
        return False


async def _test_empty_returns_nothing():
    """测试传入空列表时返回空片段，空态文案由调用方负责"""
    try:
        msg = _FakeSession(await _session("help_empty"))
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", [])])
        return parts == []
    except Exception:
        return False


async def _test_disable_joke():
    """测试标题与分隔符均不参与玩笑替换

    模块名是标识符，被替换后就无法照着输入了。
    """
    try:
        msg = _FakeSession(await _session("help_joke"))
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki", "maimai"])])
        for part in parts:
            if isinstance(part, PlainElement) and not part.disable_joke:
                return False
        return True
    except Exception:
        return False


async def _test_rendered_layout():
    """测试经适配器渲染后，标题独占一行而列表各项同处一行"""
    try:
        session_info = await _session("help_layout")
        msg = _FakeSession(session_info)
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki", "maimai"])])

        lines = [line for line in _render_lines(session_info, parts) if line]
        if len(lines) != 2:
            return False
        if lines[1] != "[wiki] | [maimai]":
            return False
        return True
    except Exception:
        return False


async def _test_degraded_keeps_module_names():
    """测试不支持的平台上降级后仍能读出模块名

    该分支只在支持指令操作时构造，降级路径本不可达，此处仅作防御性把关。
    """
    try:
        session_info = await _session("help_degrade", support_action_text=False)
        msg = _FakeSession(session_info)
        parts = build_clickable_modules(msg, [("core.message.help.legacy.base", ["wiki"])])
        sendable = MessageChain.assign(parts).as_sendable(session_info)
        text = "".join(v.text for v in sendable.values if isinstance(v, PlainElement))
        if "wiki" not in text:
            return False
        return True
    except Exception:
        return False


async def _test_multi_group_separation():
    """测试第二组起的标题带前导换行

    上一组末尾是指令操作，适配器会把紧随其后的文本拼入同一项，后续组的标题
    若不带前导换行，就会紧贴在上一组最后一个标签之后。
    """
    try:
        session_info = await _session("help_groups")
        msg = _FakeSession(session_info)
        parts = build_clickable_modules(
            msg,
            [
                ("core.message.help.legacy.base", ["help"]),
                ("core.message.help.legacy.external", ["wiki"]),
            ],
        )
        titles = [p for p in parts if isinstance(p, PlainElement) and p.text != " | "]
        if len(titles) != 2:
            return False
        if titles[0].text.startswith("\n"):
            return False
        if not titles[1].text.startswith("\n"):
            return False

        # 渲染后应为四行：两个标题各一行、两组列表各一行
        lines = [line for line in _render_lines(session_info, parts) if line]
        if len(lines) != 4:
            return False
        if lines[1] != "[help]" or lines[3] != "[wiki]":
            return False
        return True
    except Exception:
        return False


async def _test_hint_not_glued_to_module_list():
    """测试列表之后追加的提示语不会被粘在最后一个模块名后面

    可点击列表以指令操作收尾，适配器会把紧随其后的文本并入同一行。~help 与 ~module list
    都会在列表之后追加「使用……查看详细信息」一类的提示，不加收尾就会挤成一行。
    """
    session_info = await _session("help_hint")
    msg = _FakeSession(session_info)
    prefix = session_info.prefixes[0]
    help_msg = MessageChain.assign(
        build_clickable_modules(
            msg,
            [
                ("core.message.help.legacy.base", ["help"]),
                ("core.message.help.legacy.external", ["wiki", "dice"]),
            ],
        )
    )
    end_inline_run(help_msg)
    help_msg.append(I18NContext("core.message.help.detail", prefix=prefix, cmd=ActionText(f"{prefix}help ")))
    help_msg.append(I18NContext("core.message.help.all_modules", prefix=prefix, cmd=ActionText(f"{prefix}module list")))

    lines = [line for line in _render_lines(session_info, help_msg.values) if line.strip()]
    # 两个标题各一行、两组列表各一行、两条提示各一行
    if len(lines) != 6:
        Logger.error(f"Help should render 6 lines, got {len(lines)}: {lines}")
        return False
    # 模块列表所在行不得掺入提示语
    if lines[3].strip() != "[wiki] | [dice]":
        Logger.error(f"The module list line should carry modules only, got {lines[3]!r}")
        return False
    if "查看详细信息" not in lines[4] or "查看所有的可用模块" not in lines[5]:
        Logger.error(f"Both hints should stand on their own lines, got {lines[4]!r} and {lines[5]!r}")
        return False
    return True


async def _test_table_shape():
    """测试表格的行列数：高度封顶，宽度随模块数增长"""
    session_info = await _session("help_table_shape")
    msg = _FakeSession(session_info)
    cases = {
        # 模块数: (列数, 行数)。列数取「按高度上限反算」与「最少列数」之较大者
        1: (1, 1),
        2: (2, 1),
        3: (3, 1),
        4: (3, 2),
        13: (3, 5),
        25: (3, 9),
        30: (3, 10),
        40: (4, 10),
        66: (7, 10),
    }
    for count, (columns, rows) in cases.items():
        names = [f"m{i}" for i in range(count)]
        lines = [
            line for line in _render_lines(session_info, build_module_table(msg, [(TABLE_TITLE_KEY, names)])) if line
        ]
        # 首行为表头、次行为分隔行，其余为数据行
        if len(lines) != rows + 2:
            Logger.error(f"{count} modules should render {rows} data rows, got {len(lines) - 2}: {lines}")
            return False
        if lines[1] != "|" + "---|" * columns:
            Logger.error(f"{count} modules should render {columns} columns, got {lines[1]!r}")
            return False
    return True


async def _test_table_never_exceeds_max_rows():
    """测试任何模块数下高度都不突破上限

    高度失控正是上一版三列不限行被否掉的原因，此处守住不再复发。
    """
    session_info = await _session("help_table_height")
    msg = _FakeSession(session_info)
    for count in range(1, 200):
        names = [f"m{i}" for i in range(count)]
        lines = [
            line for line in _render_lines(session_info, build_module_table(msg, [(TABLE_TITLE_KEY, names)])) if line
        ]
        if len(lines) - 2 > TABLE_MAX_ROWS:
            Logger.error(f"{count} modules produced {len(lines) - 2} rows, over the limit of {TABLE_MAX_ROWS}")
            return False
    return True


async def _test_table_rows_are_uniform():
    """测试各行列数一致，末行不足处补空单元格

    markdown 要求整张表的列数齐平，末行漏补会使该行连同表格一并渲染失败。
    """
    session_info = await _session("help_table_pad")
    msg = _FakeSession(session_info)
    for count in range(1, 30):
        names = [f"m{i}" for i in range(count)]
        lines = [
            line for line in _render_lines(session_info, build_module_table(msg, [(TABLE_TITLE_KEY, names)])) if line
        ]
        widths = {line.count("|") for line in lines}
        if len(widths) != 1:
            Logger.error(f"{count} modules produced ragged rows: {lines}")
            return False
    return True


async def _test_table_cells_are_clickable():
    """测试单元格里的模块名是可点击标签，且填入的命令正确

    标签能落在单元格中间，靠的是适配器把指令操作及其后的文本并入同一项；这一条同时守住
    表格未被拆成多个元素——一旦拆开，竖线与标签会各自成行，表格随即散架。
    """
    session_info = await _session("help_table_click")
    msg = _FakeSession(session_info)
    parts = build_module_table(msg, [(TABLE_TITLE_KEY, ["wiki", "dice", "coin"])])
    actions = [p for p in parts if isinstance(p, ActionTextElement)]
    if len(actions) != 3:
        Logger.error(f"Every module name should be an action text, got {len(actions)}")
        return False
    if actions[0].text.text != f"{session_info.prefixes[0]}help wiki" or actions[0].show.text != "wiki":
        Logger.error(f"A cell should fill in the help command for its module, got {actions[0]}")
        return False
    lines = [line for line in _render_lines(session_info, parts) if line]
    if lines[2] != "| [wiki] | [dice] | [coin] |":
        Logger.error(f"The three modules should share one row, got {lines[2]!r}")
        return False
    return True


async def _test_table_empty_returns_nothing():
    """测试传入空列表时返回空片段，空态文案由调用方负责"""
    msg = _FakeSession(await _session("help_table_empty"))
    if build_module_table(msg, [(TABLE_TITLE_KEY, [])]) != []:
        Logger.error("An empty module list should produce no table at all")
        return False
    return True


async def _test_table_is_fenced_by_blank_lines():
    """测试表格前后各有一个空行

    markdown 表格靠空行终结：末尾少了它，其后的「模块作者」等行会被某些客户端的解析器
    吸进表格；开头少了它，表头会被并进上一段，表格根本不成立。两侧的表现又随客户端而异，
    正是本用例要钉死的东西。
    """
    session_info = await _session("help_table_fence")
    msg = _FakeSession(session_info)
    doc = {"args": [{"args": "~m c", "desc": "说明"}], "options": []}
    # 复刻 ~help <模块> 的组装：简介、表格、作者
    elements = [Plain("模块简介\n", disable_joke=True)]
    elements += build_command_table(msg, doc, [])
    elements.append(Plain("模块作者：someone"))

    lines = _render_lines(session_info, elements)
    if "模块简介" not in lines[0]:
        Logger.error(f"The description should lead the message, got {lines[0]!r}")
        return False
    if lines[1].strip():
        Logger.error(f"A blank line should separate the description from the table head, got {lines!r}")
        return False
    author = next(index for index, line in enumerate(lines) if "模块作者" in line)
    if lines[author - 1].strip():
        Logger.error(f"A blank line should terminate the table before the author line, got {lines!r}")
        return False
    return True


async def _test_table_does_not_end_inline():
    """测试表格以纯文本收尾

    收尾若是指令操作，调用方随后追加的元素会被并入最后一个单元格所在的行。
    """
    msg = _FakeSession(await _session("help_table_tail"))
    parts = build_module_table(msg, [(TABLE_TITLE_KEY, ["wiki", "dice"])])
    if isinstance(parts[-1], ActionTextElement):
        Logger.error("The table must not end with an action text, or the following element would be glued to it")
        return False
    if not parts[-1].text.endswith("\n"):
        Logger.error(f"The table must end with a newline so a blank line terminates it, got {parts[-1].text!r}")
        return False
    return True


async def _test_strip_command_arguments():
    """测试填入输入框的命令已去掉参数占位符

    占位符照原样填进去还得用户自行删掉，反倒碍事。可选项会嵌套（如 [-l <lang>]、[<lang>]），
    用正则逐个匹配会留下孤立的方括号，故按括号深度剔除。
    """
    cases = {
        # 不带参数的原样返回，点击后可直接发出
        "~setup list target": "~setup list target",
        # 带参数的留一个尾随空格，光标即落在参数位置
        "~3dsdb <keywords>": "~3dsdb ",
        "~coin [<amount>]": "~coin ",
        "~ab [--legacy]": "~ab ",
        "~wordle [--hard] [--trial]": "~wordle ",
        # 嵌套：选项自带参数
        "~wiki <pagename> [-l <lang>]": "~wiki ",
        "~chunithm base <constant> [<constant_max>] [-p <page>]": "~chunithm base ",
        # 变长参数同样不该留下
        "~image fillwhite ...": "~image fillwhite ",
        "~module enable <module> ...": "~module enable ",
    }
    for template, expected in cases.items():
        actual = strip_command_arguments(template)
        if actual != expected:
            Logger.error(f"{template!r} should strip to {expected!r}, got {actual!r}")
            return False
    return True


async def _test_command_table_fills_stripped_command():
    """测试表格里展示完整模板、填入的却是去掉参数后的主体"""
    session_info = await _session("help_cmd_strip")
    msg = _FakeSession(session_info)
    doc = {"args": [{"args": "~wiki <pagename> [-l <lang>]", "desc": "查询页面"}], "options": []}
    parts = build_command_table(msg, doc, [])
    actions = [p for p in parts if isinstance(p, ActionTextElement)]
    if len(actions) != 1:
        Logger.error(f"The command row should carry exactly one action text, got {len(actions)}")
        return False
    if actions[0].text.text != "~wiki ":
        Logger.error(f"The filled command should drop the placeholders, got {actions[0].text.text!r}")
        return False
    if actions[0].show.text != "~wiki <pagename> [-l <lang>]":
        Logger.error(f"The displayed text should keep the full template, got {actions[0].show.text!r}")
        return False
    return True


async def _test_command_table_escapes_pipes():
    """测试单元格里的竖线被转义

    正则中就有 ≺(.*?)≻\\|⧼(.*?)⧽ 这类内容，不转义会把该行拆出多余的列、整张表错位。
    """
    session_info = await _session("help_cmd_pipe")
    msg = _FakeSession(session_info)
    parts = build_command_table(msg, {"args": [], "options": []}, [("a|b", "说明|带竖线")])
    text = "".join(p.text for p in parts if isinstance(p, PlainElement))
    if "a\\|b" not in text or "说明\\|带竖线" not in text:
        Logger.error(f"Pipes inside cells must be escaped, got {text!r}")
        return False
    return True


async def _test_command_table_expands_columns():
    """测试命令多时由列数吸收，高度不越界

    一「列」是「命令 + 说明」一对，故实际列数为对数的两倍。命令多的模块若仍一行一条，
    表格会长到二十余行。
    """
    session_info = await _session("help_cmd_wide")
    msg = _FakeSession(session_info)
    for count, pairs in ((5, 1), (10, 1), (11, 2), (22, 3)):
        doc = {"args": [{"args": f"~m c{i}", "desc": f"说明{i}"} for i in range(count)], "options": []}
        lines = [line for line in _render_lines(session_info, build_command_table(msg, doc, [])) if line]
        rows = len(lines) - 2
        if rows > TABLE_MAX_ROWS:
            Logger.error(f"{count} commands produced {rows} rows, over the limit of {TABLE_MAX_ROWS}")
            return False
        if lines[1] != "|" + "---|" * (pairs * 2):
            Logger.error(f"{count} commands should render {pairs} command/desc pairs, got {lines[1]!r}")
            return False
    return True


async def _test_command_table_rows_are_uniform():
    """测试各行列数一致，末行补空的成对单元格

    区隔行同样要铺满整行的列数，否则该行连同表格一并渲染失败。
    """
    session_info = await _session("help_cmd_uniform")
    msg = _FakeSession(session_info)
    for count in (1, 3, 7, 12, 23):
        doc = {
            "args": [{"args": f"~m c{i}", "desc": f"说明{i}"} for i in range(count)],
            "options": [{"-p": "页数"}],
        }
        lines = [line for line in _render_lines(session_info, build_command_table(msg, doc, [("a", "b")])) if line]
        widths = {line.count("|") for line in lines}
        if len(widths) != 1:
            Logger.error(f"{count} commands produced ragged rows: {lines}")
            return False
    return True


async def _test_regex_is_wrapped_in_code():
    """测试正则包进行内代码，且不再逐字符反斜杠转义

    正则满是 * _ [] () 一类字符，直接放进单元格会被当作格式标记渲染。
    """
    session_info = await _session("help_regex_code")
    msg = _FakeSession(session_info)
    pattern = r"\[\[(.*?)\]\]"
    parts = build_command_table(msg, {"args": [], "options": []}, [(pattern, "内联查询")])
    text = "".join(p.text for p in parts if isinstance(p, PlainElement))
    if f"`{pattern}`" not in text:
        Logger.error(f"A regex should be wrapped in an inline code span, got {text!r}")
        return False
    return True


def _test_format_table_code_edge_cases() -> bool:
    """测试行内代码的三处边界：竖线、反引号、换行"""
    cases = {
        # 竖线仍须转义：表格先按竖线切分单元格，代码块拦不住它
        "a|b": "`a\\|b`",
        # 围栏须比内容里最长的一串反引号更长，否则会在中途被闭合
        "a`b": "``a`b``",
        "a``b": "```a``b```",
        # 内容以反引号起止时两侧补空格，否则会被并入围栏
        "`x`": "`` `x` ``",
        # 换行在代码块内无从表达，折成空格
        "a\nb": "`a b`",
        # 空文本不产出空围栏
        "": "",
    }
    for raw, expected in cases.items():
        actual = format_table_code(raw)
        if actual != expected:
            Logger.error(f"{raw!r} should format to {expected!r}, got {actual!r}")
            return False
    return True


async def _test_empty_group_skipped():
    """测试模块名为空的组被整组跳过，不留下孤零零的标题"""
    try:
        msg = _FakeSession(await _session("help_skip"))
        parts = build_clickable_modules(
            msg,
            [
                ("core.message.help.legacy.base", ["help"]),
                ("core.message.help.legacy.external", []),
            ],
        )
        titles = [p for p in parts if isinstance(p, PlainElement) and p.text != " | "]
        if len(titles) != 1:
            return False
        external = msg.session_info.locale.t("core.message.help.legacy.external")
        if any(external in p.text for p in parts if isinstance(p, PlainElement)):
            return False
        return True
    except Exception:
        return False


@func_case
async def test_clickable_modules(tester: Tester):
    """modules.core.help: 可点击模块列表测试"""
    await tester.test(_test_help_about_button_replaces_donate, "help 关于我们按钮测试")
    await tester.test(_test_image_help_precedes_action_text_fallback, "无表格能力时图片帮助优先测试")
    await tester.test(_test_image_flag_overrides_markdown_table, "--image 强制图片帮助测试")
    await tester.test(_test_image_template_omits_help_command, "图片内移除查看详情提示测试")
    await tester.test(_test_help_doc_template_marks_module_type_with_swatch, "模块详细帮助类型色块测试")
    await tester.test(_test_markdown_help_marks_module_type_with_emoji, "Markdown 模块详细帮助类型标记测试")
    await tester.test(_test_element_sequence, "元素交错排布测试")
    await tester.test(_test_title_ends_with_newline, "标题自带换行测试")
    await tester.test(_test_action_text_payload, "标签命令与展示文案测试")
    await tester.test(_test_module_toggle_payloads, "模块开关状态标签测试")
    await tester.test(_test_unsupported_module_strikethrough, "受限模块删除线测试")
    await tester.test(_test_module_table_group_legends, "Markdown 模块分组开关图例测试")
    await tester.test(_test_markdown_help_header, "Markdown help 顶栏测试")
    await tester.test(_test_markdown_help_header_permissions_and_width, "Markdown help 顶栏权限与列宽测试")
    await tester.test(_test_qqbot_admin_help_includes_disabled_modules, "QQBot 管理员帮助合并模块列表测试")
    await tester.test(_test_qqbot_superuser_help_header, "QQBot 超级用户顶栏权限测试")
    await tester.test(_test_qqbot_non_admin_help_keeps_module_list_button, "QQBot 非管理员保留模块列表按钮测试")
    await tester.test(_test_qqbot_admin_legacy_help_keeps_legacy_scope, "QQBot 管理员 legacy 帮助范围测试")
    await tester.test(_test_qqbot_module_list_hides_toggles_from_non_admin, "QQBot 普通用户模块列表隐藏开关测试")
    await tester.test(_test_qqbot_module_list_keeps_toggles_for_admin, "QQBot 管理员模块列表保留开关测试")
    await tester.test(_test_single_module_no_separator, "单模块无多余分隔符测试")
    await tester.test(_test_empty_returns_nothing, "空列表返回空片段测试")
    await tester.test(_test_disable_joke, "禁用玩笑替换测试")
    await tester.test(_test_rendered_layout, "渲染后分行测试")
    await tester.test(_test_multi_group_separation, "组间换行测试")
    await tester.test(_test_hint_not_glued_to_module_list, "提示语不粘连测试")
    await tester.test(_test_table_shape, "表格行列数测试")
    await tester.test(_test_table_never_exceeds_max_rows, "表格高度封顶测试")
    await tester.test(_test_table_rows_are_uniform, "表格列数齐平测试")
    await tester.test(_test_table_cells_are_clickable, "表格单元格可点击测试")
    await tester.test(_test_table_empty_returns_nothing, "表格空列表测试")
    await tester.test(_test_table_does_not_end_inline, "表格纯文本收尾测试")
    await tester.test(_test_table_is_fenced_by_blank_lines, "表格前后空行终结测试")
    await tester.test(_test_strip_command_arguments, "命令参数剥离测试")
    await tester.test(_test_command_table_fills_stripped_command, "命令表填入剥离后命令测试")
    await tester.test(_test_command_table_escapes_pipes, "单元格竖线转义测试")
    await tester.test(_test_command_table_expands_columns, "命令表列数扩展测试")
    await tester.test(_test_command_table_rows_are_uniform, "命令表列数齐平测试")
    await tester.test(_test_regex_is_wrapped_in_code, "正则包进行内代码测试")
    await tester.test(_test_format_table_code_edge_cases, "行内代码边界测试")
    await tester.test(_test_empty_group_skipped, "空组跳过测试")
    await tester.test(_test_degraded_keeps_module_names, "降级保留模块名测试")

    return tester
