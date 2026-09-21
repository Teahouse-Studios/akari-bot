"""设置面板单元测试 - 设置行的构造与渲染。"""

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester
from modules.core.common_tools.help import get_setup_button_data
from modules.core.common_tools.setup import (
    _ends_with_inline_entry,
    build_jump_buttons,
    build_sender_rows,
    build_target_rows,
    render_rows,
)


def _make_msg(
    target_data: dict | None = None,
    sender_data: dict | None = None,
    muted: bool = False,
    support_button: bool = False,
    support_markdown_toggle: bool = False,
) -> MessageSession:
    session_info = SessionInfo(
        target_id="TEST|Group|setup_panel",
        sender_id="TEST|1",
        target_from="TEST|Group",
        client_name="TEST",
        session_id="setup-panel",
        target_union_info=TargetUnionInfo(union_id="UTID|1", target_data=target_data or {}, muted=muted),
        sender_union_info=SenderUnionInfo(union_id="USID|1", sender_data=sender_data or {}),
        prefixes=["/", "~"],
        tz_offset="+8",
        support_button=support_button,
        support_action_text=True,
        support_markdown_toggle=support_markdown_toggle,
    )
    return MessageSession(session_info=session_info)


def _labels(rows) -> list[str]:
    return [row.label for row in rows]


def _row_by_label(rows, label: str):
    return next((row for row in rows if row.label == label), None)


def _render(support_button: bool = False, can_edit: bool = True) -> list:
    msg = _make_msg(support_button=support_button)
    return render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), can_edit)


def _test_sender_rows_default_to_enabled() -> bool:
    rows = build_sender_rows(_make_msg())
    if len(rows) != 2:
        Logger.error(f"Sender panel should list exactly two settings, got {len(rows)}")
        return False
    if any(row.value != "已开启" for row in rows):
        Logger.error(f"Both sender settings should default to enabled, got {[r.value for r in rows]}")
        return False
    return True


def _test_sender_rows_follow_setting() -> bool:
    rows = build_sender_rows(_make_msg(sender_data={"typing_prompt": False}))
    row = _row_by_label(rows, "输入提示")
    if not row:
        Logger.error("Sender panel should carry the typing switch")
        return False
    if row.value != "已关闭" or row.action != "开启":
        Logger.error(f"A disabled switch should read 已关闭 and offer 开启, got {row.value} / {row.action}")
        return False
    return True


def _test_target_rows_content() -> bool:
    labels = _labels(build_target_rows(_make_msg()))
    for expected in ("语言", "静音", "自定义前缀", "时间偏移", "命令冷却"):
        if expected not in labels:
            Logger.error(f"Target panel should list {expected}, got {labels}")
            return False
    return True


def _test_target_prefix_and_cooldown_defaults() -> bool:
    rows = build_target_rows(_make_msg())
    prefix_row = _row_by_label(rows, "自定义前缀")
    cooldown_row = _row_by_label(rows, "命令冷却")
    if not prefix_row or prefix_row.value != "无":
        Logger.error(f"An unset custom prefix should read 无, got {prefix_row and prefix_row.value}")
        return False
    if not cooldown_row or cooldown_row.value != "0 秒":
        Logger.error(f"Cooldown should default to 0 秒, got {cooldown_row and cooldown_row.value}")
        return False
    return True


def _test_mute_row_wording() -> bool:
    unmuted = _row_by_label(build_target_rows(_make_msg()), "静音")
    muted = _row_by_label(build_target_rows(_make_msg(muted=True)), "静音")
    if not unmuted or unmuted.value != "已关闭" or unmuted.action != "开启":
        Logger.error(f"An unmuted target should read 已关闭 and offer 开启, got {unmuted}")
        return False
    if not muted or muted.value != "已开启" or muted.action != "关闭":
        Logger.error(f"A muted target should read 已开启 and offer 关闭, got {muted}")
        return False
    return True


def _test_sign_row_follows_petal_config() -> bool:
    has_sign = _row_by_label(build_target_rows(_make_msg()), "签到") is not None
    if has_sign != CoreConfig.enable_petal:
        Logger.error(f"The sign row should appear iff enable_petal is on (enable_petal={CoreConfig.enable_petal})")
        return False
    return True


def _test_commands_carry_current_value() -> bool:
    msg = _make_msg(target_data={"cooldown_time": 5, "command_prefix": ["!"]})
    rows = build_target_rows(msg)
    expected = {
        "语言": f"setup locale {msg.session_info.target_union_info.locale}",
        "时间偏移": "setup timeoffset +8",
        "命令冷却": "setup cooldown 5",
    }
    for label, command in expected.items():
        row = _row_by_label(rows, label)
        if not row or row.command != command:
            Logger.error(f"{label} should prefill its command as {command!r}, got {row and row.command!r}")
            return False
    # 自定义前缀做的是追加而非替换，没有可预填的单值
    prefix_row = _row_by_label(rows, "自定义前缀")
    if not prefix_row or prefix_row.command != "setup prefix add ":
        Logger.error(f"The prefix entry appends rather than replaces, got {prefix_row and prefix_row.command!r}")
        return False
    return True


def _test_rows_carry_no_prefix() -> bool:
    rows = build_target_rows(_make_msg()) + build_sender_rows(_make_msg())
    for row in rows:
        if row.command.startswith(tuple(command_prefix)) or row.command.startswith("/"):
            Logger.error(f"SettingRow.command must not carry a prefix, got {row.command!r}")
            return False
    return True


def _test_every_row_gets_an_inline_entry() -> bool:
    for support_button in (True, False):
        msg = _make_msg(support_button=support_button)
        for builder, name in ((build_target_rows, "target"), (build_sender_rows, "sender")):
            rows = builder(msg)
            elements = render_rows(msg, "core.message.setup.list.target", rows, True)
            inline = [x for x in elements if isinstance(x, ActionTextElement)]
            if len(inline) != len(rows):
                Logger.error(
                    f"Every {name} row should carry an inline entry "
                    f"(support_button={support_button}), expected {len(rows)}, got {len(inline)}"
                )
                return False
    return True


def _qqbot_lines(msg: MessageSession, elements: list) -> list[str]:
    texts = []
    inline_pending = False
    for x in MessageChain.assign(elements).as_sendable(msg.session_info):
        if isinstance(x, ActionTextElement):
            tag = f"[{x.show.text}]"
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


def _test_one_line_per_setting_on_qqbot() -> bool:
    msg = _make_msg(support_button=True)
    target_rows = build_target_rows(msg)
    sender_rows = build_sender_rows(msg)
    elements = render_rows(msg, "core.message.setup.list.target", target_rows, True)
    elements += render_rows(
        msg, "core.message.setup.list.sender", sender_rows, True, after_inline=_ends_with_inline_entry(elements)
    )

    lines = _qqbot_lines(msg, elements)
    # 两个标题各一行，其余每项设置一行
    expected = 2 + len(target_rows) + len(sender_rows)
    if len(lines) != expected:
        Logger.error(f"Panel should render {expected} lines on QQBot, got {len(lines)}: {lines}")
        return False
    if any(not line.strip() for line in lines):
        Logger.error(f"Panel should contain no blank lines, got {lines}")
        return False
    return True


def _test_no_manual_newline_on_plain_platforms() -> bool:
    msg = _make_msg(support_button=False)
    msg.session_info.support_action_text = False
    elements = render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), True)
    for element in elements:
        if isinstance(element, PlainElement) and "\n" in element.text:
            Logger.error(f"Rows must not carry manual newlines on this path, got {element.text!r}")
            return False
    lines = MessageChain.assign(elements).as_sendable(msg.session_info).to_str().split("\n")
    if any(not line.strip() for line in lines):
        Logger.error(f"Panel should contain no blank lines, got {lines}")
        return False
    return True


def _test_markdown_row_follows_capability() -> bool:
    if _row_by_label(build_sender_rows(_make_msg()), "Markdown 消息"):
        Logger.error("A platform that cannot honour the switch should not offer the markdown row")
        return False
    row = _row_by_label(build_sender_rows(_make_msg(support_markdown_toggle=True)), "Markdown 消息")
    if not row:
        Logger.error("A platform that declares support_markdown_toggle should offer the markdown row")
        return False
    if row.command != "setup markdown":
        Logger.error(f"The markdown row should point at setup markdown, got {row.command!r}")
        return False
    if row.value != "已开启" or row.action != "关闭":
        Logger.error(f"An unset preference means markdown is on, got {row.value} / {row.action}")
        return False
    return True


def _test_markdown_row_follows_setting() -> bool:
    msg = _make_msg(sender_data={"use_markdown": False}, support_markdown_toggle=True)
    row = _row_by_label(build_sender_rows(msg), "Markdown 消息")
    if not row or row.value != "已关闭" or row.action != "开启":
        Logger.error(f"A disabled markdown switch should offer to turn it back on, got {row}")
        return False
    return True


def _test_invalid_prompt_row() -> bool:
    on = _row_by_label(build_target_rows(_make_msg()), "“模块不存在”提示")
    if not on or on.command != "setup invalid-module-prompt":
        Logger.error(f"The target panel should carry the invalid-module switch, got {on}")
        return False
    if on.value != "已开启":
        Logger.error(f"An unset switch means the prompt is on, got {on.value}")
        return False
    off = _row_by_label(build_target_rows(_make_msg(target_data={"invalid_module_prompt": False})), "“模块不存在”提示")
    if not off or off.value != "已关闭":
        Logger.error(f"A disabled switch should read 已关闭, got {off and off.value}")
        return False
    return True


def _test_no_entries_without_permission() -> bool:
    elements = _render(support_button=True, can_edit=False)
    if any(isinstance(x, ActionTextElement) for x in elements):
        Logger.error("A user without permission should get no interactive entries at all")
        return False
    keys = [x.key for x in elements if hasattr(x, "key")]
    if "core.message.setup.list.readonly" not in keys:
        Logger.error(f"The read-only notice should be present, got {keys}")
        return False
    return True


def _test_inline_commands_use_session_prefix() -> bool:
    msg = _make_msg(support_button=True)
    elements = render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), True)
    for element in elements:
        if isinstance(element, ActionTextElement) and not element.text.text.startswith(msg.session_info.prefixes[0]):
            Logger.error(f"Inline entry must use the session prefix, got {element.text.text!r}")
            return False
    return True


def _test_rows_are_joke_proof_and_spaced() -> bool:
    # 首个纯文本元素是分组标题，它不带入口，无须留空格
    rows = [x for x in _render() if isinstance(x, PlainElement)][1:]
    if not rows:
        Logger.error("The panel should render one plain element per setting")
        return False
    for row in rows:
        if not row.disable_joke:
            Logger.error(f"Row {row.text!r} must disable joke substitution to protect the command text")
            return False
        if not row.text.endswith(" "):
            Logger.error(f"Row {row.text!r} must end with a space so the inline entry does not run into it")
            return False
    return True


def _test_jump_buttons() -> bool:
    msg = _make_msg(support_button=True)
    to_sender = build_jump_buttons(msg, show_target=True, show_sender=False)
    to_target = build_jump_buttons(msg, show_target=False, show_sender=True)
    if to_sender != [("💬 用户设置", f"{command_prefix[0]}setup list sender")]:
        Logger.error(f"Listing the target domain should offer a jump to the sender panel, got {to_sender}")
        return False
    if to_target != [("👥 场景设置", f"{command_prefix[0]}setup list target")]:
        Logger.error(f"Listing the sender domain should offer a jump to the target panel, got {to_target}")
        return False
    if build_jump_buttons(msg, show_target=True, show_sender=True):
        Logger.error("Listing both domains leaves nowhere to jump to")
        return False
    return True


def _test_jump_buttons_absent_without_support() -> bool:
    msg = _make_msg(support_button=False)
    if build_jump_buttons(msg, show_target=True, show_sender=False):
        Logger.error("A session without button support should get no jump button")
        return False
    return True


def _test_help_buttons_present() -> bool:
    rows = get_setup_button_data(_make_msg(support_button=True))
    commands = [button.value for row in rows for button in row.buttons]
    expected = [f"{command_prefix[0]}setup list target", f"{command_prefix[0]}setup list sender"]
    if commands != expected:
        Logger.error(f"Help should offer both panel entries as {expected}, got {commands}")
        return False
    # 文案须取自按钮专设的键：面板标题带有分隔用的方括号，套进按钮里并不好看
    labels = [button.show for row in rows for button in row.buttons]
    if labels != ["👥 场景设置", "💬 用户设置"]:
        Logger.error(f"Help button labels should carry no bracket decoration, got {labels}")
        return False
    return True


def _test_help_buttons_absent_without_support() -> bool:
    if get_setup_button_data(_make_msg(support_button=False)) != []:
        Logger.error("A session without button support should get no help buttons")
        return False
    return True


@func_case
async def test_setup_panel(tester: Tester):
    """modules.core.common_tools.setup: 设置面板构造测试"""
    await tester.test(_test_sender_rows_default_to_enabled, "个人设置默认开启测试")
    await tester.test(_test_sender_rows_follow_setting, "个人设置跟随取值测试")
    await tester.test(_test_target_rows_content, "场景设置内容测试")
    await tester.test(_test_target_prefix_and_cooldown_defaults, "场景设置默认值测试")
    await tester.test(_test_mute_row_wording, "静音项措辞测试")
    await tester.test(_test_sign_row_follows_petal_config, "签到项随配置测试")
    await tester.test(_test_markdown_row_follows_capability, "markdown 项随能力测试")
    await tester.test(_test_markdown_row_follows_setting, "markdown 项跟随取值测试")
    await tester.test(_test_invalid_prompt_row, "模块不存在提示项测试")
    await tester.test(_test_commands_carry_current_value, "命令预填当前值测试")
    await tester.test(_test_rows_carry_no_prefix, "设置行不含前缀测试")
    await tester.test(_test_every_row_gets_an_inline_entry, "每行均有入口测试")
    await tester.test(_test_one_line_per_setting_on_qqbot, "QQ 上每项独占一行测试")
    await tester.test(_test_no_manual_newline_on_plain_platforms, "降级平台不多换行测试")
    await tester.test(_test_no_entries_without_permission, "无权限无入口测试")
    await tester.test(_test_inline_commands_use_session_prefix, "行内用会话前缀测试")
    await tester.test(_test_rows_are_joke_proof_and_spaced, "行文本防替换与留空测试")
    await tester.test(_test_jump_buttons, "跨域跳转按钮测试")
    await tester.test(_test_jump_buttons_absent_without_support, "无按钮能力时无跳转测试")
    await tester.test(_test_help_buttons_present, "help 挂按钮测试")
    await tester.test(_test_help_buttons_absent_without_support, "无按钮能力时 help 不挂按钮测试")

    return tester
