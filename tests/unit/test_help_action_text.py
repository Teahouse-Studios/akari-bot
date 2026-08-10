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
from core.builtins.message.elements import ActionTextElement, ImageElement, PlainElement
from core.builtins.message.internal import ActionText, I18NContext, Image, Plain
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.constants.exceptions import SessionFinished
from core.logger import Logger
from core.tester import func_case, Tester
from core.utils.table import TABLE_MAX_ROWS, format_table_code
from modules.core.help import (
    build_clickable_modules,
    build_command_table,
    build_module_table,
    end_inline_run,
    env,
    help_overview,
    modules_list_help,
    strip_command_arguments,
)

# 表格测试所用的表头键，此处不校验其内容，只借它走通渲染
TABLE_TITLE_KEY = "core.message.help.table.title"


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
    """图片帮助页不再内嵌查看详情命令，该提示由图片外的 ActionText 承担。"""
    locale = (await _session("help_image_template")).locale
    rendered = await env.get_template("module_list.html").render_async(
        msg=SimpleNamespace(session_info=SimpleNamespace(prefixes=["~"])),
        locale=locale,
        CommandParser=None,
        is_base_superuser=False,
        is_superuser=False,
        len=len,
        module_list={},
        show_disabled_modules=False,
        target_enabled_list=[],
        use_font_mirror=False,
    )
    return "${cmd}" not in rendered and "~help " not in rendered and "模块名称" not in rendered


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
    await tester.test(_test_image_help_precedes_action_text_fallback, "无表格能力时图片帮助优先测试")
    await tester.test(_test_image_flag_overrides_markdown_table, "--image 强制图片帮助测试")
    await tester.test(_test_image_template_omits_help_command, "图片内移除查看详情提示测试")
    await tester.test(_test_element_sequence, "元素交错排布测试")
    await tester.test(_test_title_ends_with_newline, "标题自带换行测试")
    await tester.test(_test_action_text_payload, "标签命令与展示文案测试")
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
