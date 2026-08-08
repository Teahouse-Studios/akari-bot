"""设置面板单元测试 - 设置行的构造与渲染。

面板把每一项设置抽象为 SettingRow，取值与入口文案在构造时即翻译完毕，渲染只管排版。
每一行的入口都挂在自己那一行上，底部键盘只承担跨域跳转 —— 两者的前缀不可混用：行内指令
操作填入的是用户正在使用的输入框，故取会话前缀；按钮回流经 interaction 另建会话，取不到
平台入口前缀，故须用全局前缀。这两条前缀不变量正是本文件守住的重点。
"""

from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ActionTextElement, PlainElement
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.config.base import CoreConfig
from core.database.models import SenderUnionInfo, TargetUnionInfo
from core.logger import Logger
from core.tester import func_case, Tester
from modules.core.help import get_setup_button_data
from modules.core.setup import (
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
    """构造一个可供面板取值的消息会话。

    直接构造 SessionInfo 而非经 assign()，以免用例之间共用 union 数据。tz_offset 须显式给出：
    该字段的解析发生在 assign() 中，直接构造时取默认值 None。

    :param target_data: 场景数据。
    :param sender_data: 用户数据。
    :param muted: 场景是否已静音。
    :param support_button: 会话是否具备按钮能力。
    :param support_markdown_toggle: 平台是否允许用户自行关闭 markdown 消息。
    :return: 消息会话。
    """
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
    """取各行的设置名。

    :param rows: 设置行列表。
    :return: 设置名列表。
    """
    return [row.label for row in rows]


def _row_by_label(rows, label: str):
    """按设置名取出对应的设置行。

    :param rows: 设置行列表。
    :param label: 设置名。
    :return: 匹配的设置行，无匹配时为 None。
    """
    return next((row for row in rows if row.label == label), None)


def _render(support_button: bool = False, can_edit: bool = True) -> list:
    """渲染场景面板并取回消息元素。

    :param support_button: 会话是否具备按钮能力。
    :param can_edit: 当前用户是否可以修改这一组设置。
    :return: 消息元素列表。
    """
    msg = _make_msg(support_button=support_button)
    return render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), can_edit)


def _test_sender_rows_default_to_enabled() -> bool:
    """用户未设置过时，两项个人设置均为开启"""
    rows = build_sender_rows(_make_msg())
    if len(rows) != 2:
        Logger.error(f"Sender panel should list exactly two settings, got {len(rows)}")
        return False
    if any(row.value != "已开启" for row in rows):
        Logger.error(f"Both sender settings should default to enabled, got {[r.value for r in rows]}")
        return False
    return True


def _test_sender_rows_follow_setting() -> bool:
    """关闭后取值与入口文案须同步反转"""
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
    """场景面板须含语言、静音、前缀、时间偏移、命令冷却五项常驻设置"""
    labels = _labels(build_target_rows(_make_msg()))
    for expected in ("语言", "静音", "自定义前缀", "时间偏移", "命令冷却"):
        if expected not in labels:
            Logger.error(f"Target panel should list {expected}, got {labels}")
            return False
    return True


def _test_target_prefix_and_cooldown_defaults() -> bool:
    """未设置自定义前缀时显示「无」，冷却时间默认为 0 秒"""
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
    """测试静音项与其余开关一致：取值为已开启／已关闭，入口文案取当前状态之反"""
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
    """签到项随花瓣功能的开关出现或隐去，与 setup sign 的 load 判据一致"""
    has_sign = _row_by_label(build_target_rows(_make_msg()), "签到") is not None
    if has_sign != CoreConfig.enable_petal:
        Logger.error(f"The sign row should appear iff enable_petal is on (enable_petal={CoreConfig.enable_petal})")
        return False
    return True


def _test_commands_carry_current_value() -> bool:
    """带参数的命令须附上当前取值，使点击后输入框里就是现设定"""
    msg = _make_msg(target_data={"cooldown_time": 5, "command_prefix": ["!"]})
    rows = build_target_rows(msg)
    expected = {
        "语言": f"locale {msg.session_info.target_union_info.locale}",
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
    if not prefix_row or prefix_row.command != "prefix add ":
        Logger.error(f"The prefix entry appends rather than replaces, got {prefix_row and prefix_row.command!r}")
        return False
    return True


def _test_rows_carry_no_prefix() -> bool:
    """设置行只存不含前缀的命令，前缀由渲染阶段按用途补上"""
    rows = build_target_rows(_make_msg()) + build_sender_rows(_make_msg())
    for row in rows:
        if row.command.startswith(tuple(command_prefix)) or row.command.startswith("/"):
            Logger.error(f"SettingRow.command must not carry a prefix, got {row.command!r}")
            return False
    return True


def _test_every_row_gets_an_inline_entry() -> bool:
    """每一行设置都须在自己那一行上带有入口，开关也不例外

    入口若只出现在底部键盘，用户得自行把按钮与上方的设置行对应起来；全是开关的个人设置区
    更会整段读成纯状态文字。
    """
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
    """按 QQ 适配器的规则把元素列表折成行。

    复刻 ``bots/qqbot/context.py`` 中 send_msg_markdown() 的组装：指令操作并入上一项，
    且其后紧随的文本同样并入上一项（``inline_pending``），最后以换行连接各项。该函数绑在
    平台 SDK 上，模块侧无从直接调用，故此处按同样的规则建模——面板塌成一行正是栽在这里，
    而通用的 to_str() 不复现这条规则，光看它测不出来。

    :param msg: 消息会话，用于将消息链转为可发送形态。
    :param elements: 待折行的消息元素。
    :return: 折行后的文本行。
    """
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
    """每一项设置在 QQ 上须各占一行

    指令操作会使适配器把紧随其后的文本并入同一行，换行若交由适配器按元素处理，整个面板
    会塌成一行。故此路径下的换行必须写进文本自身。
    """
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
    """不支持指令操作的平台不得自带换行

    该路径下指令操作已在消息链阶段并入前一个文本元素，各行本就是独立元素，再写换行
    只会多出空行。
    """
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
    """markdown 开关仅在平台允许时出现在个人设置中"""
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
    """关闭后取值与入口文案须同步反转"""
    msg = _make_msg(sender_data={"use_markdown": False}, support_markdown_toggle=True)
    row = _row_by_label(build_sender_rows(msg), "Markdown 消息")
    if not row or row.value != "已关闭" or row.action != "开启":
        Logger.error(f"A disabled markdown switch should offer to turn it back on, got {row}")
        return False
    return True


def _test_invalid_prompt_row() -> bool:
    """「模块不存在」提示是场景域的开关，取值随场景设置反转"""
    on = _row_by_label(build_target_rows(_make_msg()), "“模块不存在”提示")
    if not on or on.command != "setup invalid_module_prompt":
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
    """无权限时只剩状态文字，且附上权限提示"""
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
    """行内指令操作须用当前会话的前缀，它填入的是用户正在使用的输入框"""
    msg = _make_msg(support_button=True)
    elements = render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), True)
    for element in elements:
        if isinstance(element, ActionTextElement) and not element.text.text.startswith(msg.session_info.prefixes[0]):
            Logger.error(f"Inline entry must use the session prefix, got {element.text.text!r}")
            return False
    return True


def _test_rows_are_joke_proof_and_spaced() -> bool:
    """行文本须关闭玩笑替换并留出行尾空格

    指令操作降级为纯文本后会并入前一个文本元素，合并时既不补分隔符，也会连同命令原文
    一起参与玩笑替换，两者缺一都会使降级平台上的命令抄不下来。
    """
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
    """只列一域时补一个跳往另一域的按钮，两域同列则无处可跳"""
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
    """不支持按钮的平台不下发跳转按钮，以免构造出无人读取的数据"""
    msg = _make_msg(support_button=False)
    if build_jump_buttons(msg, show_target=True, show_sender=False):
        Logger.error("A session without button support should get no jump button")
        return False
    return True


def _test_help_buttons_present() -> bool:
    """支持按钮的平台上，help 菜单底部给出两个直达面板的按钮"""
    rows = get_setup_button_data(_make_msg(support_button=True))
    commands = [command for row in rows for command in row.values()]
    expected = [f"{command_prefix[0]}setup list target", f"{command_prefix[0]}setup list sender"]
    if commands != expected:
        Logger.error(f"Help should offer both panel entries as {expected}, got {commands}")
        return False
    # 文案须取自按钮专设的键：面板标题带有分隔用的方括号，套进按钮里并不好看
    labels = [label for row in rows for label in row]
    if labels != ["👥 场景设置", "💬 用户设置"]:
        Logger.error(f"Help button labels should carry no bracket decoration, got {labels}")
        return False
    return True


def _test_help_buttons_absent_without_support() -> bool:
    """不支持按钮的平台不下发按钮，以免构造出无人读取的数据"""
    if get_setup_button_data(_make_msg(support_button=False)) != []:
        Logger.error("A session without button support should get no help buttons")
        return False
    return True


@func_case
async def test_setup_panel(tester: Tester):
    """modules.core.setup: 设置面板构造测试"""
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
