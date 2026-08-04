from attrs import define

from core.builtins.bot import Bot
from core.builtins.message.elements import ActionTextElement
from core.builtins.message.internal import ActionText, I18NContext, Plain
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.i18n import Locale
from core.utils.button import arrange_buttons

setup = module("setup", base=True, desc="{I18N:core.help.setup.desc}", doc=True, alias="toggle")


@setup.command("typing {{I18N:core.help.setup.typing}}")
async def _(msg: Bot.MessageSession):
    if not msg.session_info.sender_union_info.sender_data.get("typing_prompt", True):
        await msg.session_info.sender_union_info.edit_sender_data("typing_prompt", True)
        await msg.finish(I18NContext("core.message.setup.typing.enable"))
    else:
        await msg.session_info.sender_union_info.edit_sender_data("typing_prompt", False)
        await msg.finish(I18NContext("core.message.setup.typing.disable"))


@setup.command("check {{I18N:core.help.setup.check}}")
async def _(msg: Bot.MessageSession):
    if not msg.session_info.sender_union_info.sender_data.get("typo_check", True):
        await msg.session_info.sender_union_info.edit_sender_data("typo_check", True)
        await msg.finish(I18NContext("core.message.setup.check.enable"))
    else:
        await msg.session_info.sender_union_info.edit_sender_data("typo_check", False)
        await msg.finish(I18NContext("core.message.setup.check.disable"))


@setup.command("sign {{I18N:core.help.setup.sign}}", required_admin=True, load=CoreConfig.enable_petal)
async def _(msg: Bot.MessageSession):
    if not msg.session_info.target_union_info.target_data.get("petal_sign", True):
        await msg.session_info.target_union_info.edit_target_data("petal_sign", True)
        await msg.finish(I18NContext("core.message.setup.sign.enable"))
    else:
        await msg.session_info.target_union_info.edit_target_data("petal_sign", False)
        await msg.finish(I18NContext("core.message.setup.sign.disable"))


@setup.command("timeoffset <offset> {{I18N:core.help.setup.timeoffset}}", required_admin=True)
async def _(msg: Bot.MessageSession, offset: str):
    try:
        tstr_split = [int(part) for part in offset.split(":")]
        hour = tstr_split[0]
        minute = tstr_split[1] if len(tstr_split) > 1 else 0
        if hour > 12 or minute >= 60:
            raise ValueError
        offset = f"{hour:+}" if minute == 0 else f"{hour:+}:{abs(minute):02d}"
    except ValueError:
        await msg.finish(I18NContext("core.message.setup.timeoffset.invalid"))
    await msg.session_info.target_union_info.edit_target_data("timezone_offset", offset)
    await msg.finish(I18NContext("core.message.setup.timeoffset.success", offset="" if offset == "+0" else offset))


@setup.command("cooldown <second> {{I18N:core.help.setup.cooldown}}", required_admin=True)
async def _(msg: Bot.MessageSession, second: int):
    second = 0 if second < 0 else second
    await msg.session_info.target_union_info.edit_target_data("cooldown_time", second)
    await msg.finish(I18NContext("core.message.setup.cooldown.success", time=second))


@setup.command("invalid_module_prompt {{I18N:core.help.setup.invalid_module_prompt}}", required_admin=True)
async def _(msg: Bot.MessageSession):
    if not msg.session_info.invalid_module_prompt_enabled:
        await msg.session_info.target_union_info.edit_target_data("invalid_module_prompt", True)
        await msg.finish(I18NContext("core.message.setup.invalid_module_prompt.enable"))
    else:
        await msg.session_info.target_union_info.edit_target_data("invalid_module_prompt", False)
        await msg.finish(I18NContext("core.message.setup.invalid_module_prompt.disable"))


# 不加 available_for：框架只能按平台名过滤命令，无法按会话特性过滤。若改用平台名，
# 将来其他平台声明了 support_markdown_toggle，面板会出现「有此行、命令却不可用」的死行。
# 以能力标志作唯一判据可避免该情形，代价是其他平台的帮助列表中仍会列出这条命令。
@setup.command("markdown {{I18N:core.help.setup.markdown}}")
async def _(msg: Bot.MessageSession):
    if not msg.session_info.support_markdown_toggle:
        await msg.finish(I18NContext("core.message.setup.markdown.unsupported"))
    if not msg.session_info.sender_union_info.sender_data.get("use_markdown", True):
        await msg.session_info.sender_union_info.edit_sender_data("use_markdown", True)
        await msg.finish(I18NContext("core.message.setup.markdown.enable"))
    else:
        await msg.session_info.sender_union_info.edit_sender_data("use_markdown", False)
        await msg.finish(I18NContext("core.message.setup.markdown.disable"))


@define
class SettingRow:
    """
    面板中的一行设置。

    各字段均为已翻译的字符串：模块运行于服务端进程，会话语言在此已经确定，就地翻译
    可使渲染阶段只关心排版。取值若留作消息元素，还会在充当 :class:`I18NContext` 的
    参数时被强制转为字符串字面量（见 ``core/builtins/message/chain.py`` 的参数翻译一段）。

    :param label: 设置名。
    :param value: 当前取值。
    :param action: 交互入口上展示的文案。
    :param command: 不含前缀的完整命令，尽可能带上当前取值，前缀由渲染阶段补上。
    """

    label: str
    value: str
    action: str
    command: str


def _toggle_row(locale: Locale, name_key: str, enabled: bool, command: str) -> SettingRow:
    """
    构造一个开关型设置行，其取值与入口文案按当前状态选定。

    :param locale: 会话语言。
    :param name_key: 设置名的多语言键。
    :param enabled: 当前是否开启。
    :param command: 不含前缀的切换命令。
    :return: 设置行。
    """
    name = locale.t(name_key)
    return SettingRow(
        label=name,
        value=locale.t("core.message.setup.list.value.on" if enabled else "core.message.setup.list.value.off"),
        # 入口文案取当前状态之反：已开启时能做的是关闭
        action=locale.t("core.message.setup.list.action.off" if enabled else "core.message.setup.list.action.on"),
        command=command,
    )


def build_target_rows(msg: Bot.MessageSession) -> list[SettingRow]:
    """
    构造场景域的设置行。

    语言、静音、自定义前缀三项由 locale、mute、prefix 三个模块各自维护，此处只读取其状态
    并给出入口，不重复实现切换逻辑。

    带参数的命令一律附上当前取值，使点击后输入框里就是现设定，改动何处一目了然。
    自定义前缀是例外：它承载的是一个列表，且入口做的是追加而非替换，没有可预填的单值。

    :param msg: 消息会话。
    :return: 设置行列表。
    """
    locale = msg.session_info.locale
    target_union_info = msg.session_info.target_union_info
    target_data = target_union_info.target_data
    muted = bool(target_union_info.muted)
    prefixes = target_data.get("command_prefix") or []
    tz_offset = msg.session_info._tz_offset
    cooldown = int(target_data.get("cooldown_time", 0))

    rows = [
        SettingRow(
            label=locale.t("core.message.setup.list.item.locale"),
            value=locale.t("language"),
            action=locale.t("core.message.setup.list.action.modify"),
            command=f"locale {target_union_info.locale}",
        ),
        _toggle_row(
            locale,
            "core.message.setup.list.item.mute",
            muted,
            "mute",
        ),
        SettingRow(
            label=locale.t("core.message.setup.list.item.prefix"),
            value=locale.t("message.delimiter").join(prefixes) or locale.t("message.none"),
            action=locale.t("core.message.setup.list.action.add"),
            command="prefix add ",
        ),
    ]

    if CoreConfig.enable_petal:
        rows.append(
            _toggle_row(
                locale,
                "core.message.setup.list.item.sign",
                target_data.get("petal_sign", True),
                "setup sign",
            )
        )

    rows += [
        SettingRow(
            label=locale.t("core.message.setup.list.item.timeoffset"),
            value=locale.t("core.message.setup.list.value.timeoffset", offset="" if tz_offset == "+0" else tz_offset),
            action=locale.t("core.message.setup.list.action.modify"),
            command=f"setup timeoffset {tz_offset}",
        ),
        SettingRow(
            label=locale.t("core.message.setup.list.item.cooldown"),
            value=locale.t("core.message.setup.list.value.cooldown", time=cooldown),
            action=locale.t("core.message.setup.list.action.modify"),
            command=f"setup cooldown {cooldown}",
        ),
        _toggle_row(
            locale,
            "core.message.setup.list.item.invalid_module_prompt",
            msg.session_info.invalid_module_prompt_enabled,
            "setup invalid_module_prompt",
        ),
    ]
    return rows


def build_sender_rows(msg: Bot.MessageSession) -> list[SettingRow]:
    """
    构造个人域的设置行。

    两项均为随用户走的个人偏好，在任何场景中都由用户自行决定，不受管理员管辖。

    :param msg: 消息会话。
    :return: 设置行列表。
    """
    locale = msg.session_info.locale
    sender_data = msg.session_info.sender_union_info.sender_data
    rows = [
        _toggle_row(
            locale,
            "core.message.setup.list.item.typing",
            sender_data.get("typing_prompt", True),
            "setup typing",
        ),
        _toggle_row(
            locale,
            "core.message.setup.list.item.check",
            sender_data.get("typo_check", True),
            "setup check",
        ),
    ]
    if msg.session_info.support_markdown_toggle:
        rows.append(
            _toggle_row(
                locale,
                "core.message.setup.list.item.markdown",
                sender_data.get("use_markdown", True),
                "setup markdown",
            ),
        )
    return rows


def _ends_with_inline_entry(elements: list) -> bool:
    """
    判断元素列表是否以行内入口收尾。

    适配器会把紧随行内入口之后的文本并入同一行，故其后的元素须自带换行。

    :param elements: 已积累的消息元素。
    :return: 末元素是否为行内入口。
    """
    return bool(elements) and isinstance(elements[-1], ActionTextElement)


def render_rows(
    msg: Bot.MessageSession,
    title_key: str,
    rows: list[SettingRow],
    can_edit: bool,
    after_inline: bool = False,
) -> list:
    """
    将设置行渲染为消息元素。

    每一行都在行尾挂上指令操作，点击即把命令连同当前取值填入输入框。开关不另设底部按钮：
    按钮虽能一键切换，却与所属的设置行相隔一段距离，需要用户自行对应；把入口一律放回各自
    那一行，整个面板的读法才是一致的。不支持指令操作的平台由消息链自动降级为纯文本，
    模块侧无须再分支。

    换行的写法随平台而分：指令操作在支持它的平台上会作为独立元素留给适配器，而适配器会把
    紧随其后的文本一并并入上一行（见 ``bots/qqbot/context.py`` 的 ``inline_pending``），
    换行若交由适配器按元素处理，整个面板会塌成一行，故此路径下须把换行写进文本自身。
    降级平台上指令操作已在消息链阶段并入前一个文本元素，各行本就是独立元素，再写换行反倒
    会多出空行。标题同样以纯文本构造而非 :class:`I18NContext`，正是为了能在其前补上换行。

    :param msg: 消息会话。
    :param title_key: 分组标题的多语言键。
    :param rows: 设置行列表。
    :param can_edit: 当前用户是否可以修改这一组设置。
    :param after_inline: 本组之前是否紧跟着一个行内入口，为真时标题须自带换行。
    :return: 消息元素列表。
    """
    session_info = msg.session_info
    locale = session_info.locale
    prefix = session_info.prefixes[0]
    manual_newline = can_edit and session_info.support_action_text

    title = locale.t(title_key)
    elements = [Plain(f"\n{title}" if after_inline and session_info.support_action_text else title, disable_joke=True)]
    if not can_edit:
        elements.append(I18NContext("core.message.setup.list.readonly"))

    for row in rows:
        text = locale.t("core.message.setup.list.row", name=row.label, value=row.value)
        # 首行紧随标题，标题不是行内入口，不会被并行；其后各行才需要自带换行
        lead = "\n" if manual_newline and _ends_with_inline_entry(elements) else ""
        # 行尾空格：指令操作无论以元素形态并入还是降级为纯文本，都不会自行补分隔符。
        # disable_joke 亦不可省：降级后的命令原文会并入本元素，被替换后就无法照抄了。
        elements.append(Plain(f"{lead}{text} " if can_edit else f"{lead}{text}", disable_joke=True))
        if can_edit:
            elements.append(ActionText(f"{prefix}{row.command}", show=row.action))
    return elements


def build_jump_buttons(msg: Bot.MessageSession, show_target: bool, show_sender: bool) -> list[tuple[str, str]]:
    """
    构造跳往另一个域的按钮。

    底部键盘只承担跨域跳转，各设置的入口都在自己那一行上。两域同列时无处可跳，返回空列表。

    按钮点击后经 interaction 事件另行建立会话，该会话的可用前缀取自全局配置，并不包含
    各平台在常规消息入口所用的前缀，故此处须使用 command_prefix 而非会话前缀。文案取自
    按钮专设的键，而非面板标题：后者带有分隔用的方括号，套进按钮里并不好看。

    :param msg: 消息会话。
    :param show_target: 本次是否列出了场景域。
    :param show_sender: 本次是否列出了个人域。
    :return: （标签, 命令）序列。
    """
    if not msg.session_info.support_button or show_target == show_sender:
        return []
    other = "sender" if show_target else "target"
    return [
        (
            msg.session_info.locale.t(f"core.message.setup.list.button.{other}"),
            f"{command_prefix[0]}setup list {other}",
        )
    ]


@setup.command(
    "list {{I18N:core.help.setup.list}}",
    "list target {{I18N:core.help.setup.list.target}}",
    "list sender {{I18N:core.help.setup.list.sender}}",
)
async def _(msg: Bot.MessageSession):
    show_target = "target" in msg.parsed_msg
    show_sender = "sender" in msg.parsed_msg
    # 不指定域时两域同列，一条命令即可看全
    if not show_target and not show_sender:
        show_target = show_sender = True

    # 只读展示对所有人开放，能否修改才看权限
    is_admin = await msg.check_permission()
    elements = []

    if show_target:
        elements += render_rows(msg, "core.message.setup.list.target", build_target_rows(msg), is_admin)
    if show_sender:
        # 场景组末尾若留有行内入口，个人组的标题会被适配器并入那一行
        elements += render_rows(
            msg,
            "core.message.setup.list.sender",
            build_sender_rows(msg),
            True,
            after_inline=_ends_with_inline_entry(elements),
        )

    await msg.finish(elements, button_data=arrange_buttons(build_jump_buttons(msg, show_target, show_sender)))
