import math
import re
from html import escape

from jinja2 import FileSystemLoader, Environment

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import ImageElement
from core.builtins.message.internal import ActionText, I18NContext, Plain, Url
from core.builtins.parser.command import CommandParser
from core.builtins.utils import command_prefix
from core.component import module
from core.config.base import CoreConfig
from core.constants.path import templates_path
from core.loader import ModulesManager
from core.logger import Logger
from core.utils.button import arrange_buttons
from core.utils.cache import random_cache_path
from core.utils.image import cb64imglst
from core.web_render import web_render, ElementScreenshotOptions

env = Environment(loader=FileSystemLoader(templates_path), autoescape=True, enable_async=True)
help_url = CoreConfig.help_url
donate_url = CoreConfig.donate_url
use_font_mirror = CoreConfig.use_font_mirror

hlp = module("help", base=True, doc=True)


def build_clickable_modules(msg: Bot.MessageSession, groups: list[tuple[str, list[str]]]) -> list:
    """
    把若干组模块名构造成可点击的消息链片段。

    每个模块名成为一个指令操作元素，点击后向输入框填入 `<前缀>help <模块名>`，
    省去用户照着列表手动输入的一步。

    标题以纯文本构造并自带换行，而非交由 I18NContext 延迟翻译：适配器渲染时会把
    指令操作无条件拼入上一项，标题若不带换行，模块列表会被挤到标题同一行，
    与既有的纯文本版排版不符。同理，第二组起的标题还须带前导换行，
    否则会紧贴在上一组末尾的标签之后。

    标题与分隔符均不参与玩笑替换 —— 模块名是标识符，被替换后就无法照着输入了。

    :param msg: 消息会话。
    :param groups: (标题多语言键, 模块名列表) 的序列，模块名为空的组会被跳过。
    :return: 消息元素列表；所有组皆空时返回空片段，空态文案由调用方负责。
    """
    prefix = msg.session_info.prefixes[0]
    parts = []
    for title_key, names in groups:
        if not names:
            continue
        leading = "\n" if parts else ""
        parts.append(Plain(leading + msg.session_info.locale.t(title_key) + "\n", disable_joke=True))
        for index, name in enumerate(names):
            if index:
                parts.append(Plain(" | ", disable_joke=True))
            parts.append(ActionText(f"{prefix}help {name}", show=name))
    return parts


def end_inline_run(chain: MessageChain) -> None:
    """
    终止行内连排，使其后追加的元素能各自成行。

    可点击的模块列表以指令操作收尾，而适配器会把紧随指令操作之后的文本并入同一行
    （见 ``bots/qqbot/context.py`` 中 send_msg_markdown() 的 ``inline_pending``）。
    该规则本是为「文字 + 标签 + 收尾文字」这类同出一句话的场合而设，跨消息元素时却会
    把调用方随后追加的提示语粘在最后一个模块名之后。补一个纯文本片段即可断开连排。

    片段取一个空格而非空串：消息链会把空文本换成错误提示（见
    ``core/builtins/message/chain.py`` 对空文本的处理）。换行同样不可取——适配器随后
    仍会按元素补一次换行，两者叠加会多出一个空行。

    本函数只在具备指令操作能力的平台上有意义，调用点均已由 ``use_clickable`` 把关。

    :param chain: 待收尾的消息链，就地修改。
    """
    chain.append(Plain(" ", disable_joke=True))


# 模块表格的高度上限。模块数增长时由列数吸收，使表格恒为「至多五行、按需加宽」。
MODULE_TABLE_MAX_ROWS = 5

# 模块表格的最少列数。模块寥寥时若仍按高度上限反算列数会得到单列竖排，与宽表的用意相悖。
MODULE_TABLE_MIN_COLUMNS = 3


def build_module_table(msg: Bot.MessageSession, title_key: str, names: list[str]) -> list:
    """
    把模块名排成一张 markdown 宽表。

    表格至多 :data:`MODULE_TABLE_MAX_ROWS` 行，模块数的增长由列数吸收，使消息高度大体恒定。
    末行不足处补空单元格 —— markdown 要求各行的列数一致。

    模块名做成指令操作，点击即把 ``<前缀>help <模块名>`` 填入输入框。标签之所以能落在单元格
    中间，靠的正是适配器把指令操作及其后的文本一并并入上一项的行为（见
    ``bots/qqbot/context.py`` 的 ``inline_pending``）：整张表因此累积成一个文本块，
    竖线与换行均由此处显式写出。也正因如此，本函数的产出只在同时支持 markdown 与指令操作的
    平台上成立，纯文本平台会把表格标记原样读出，调用点须自行把关。

    :param msg: 消息会话。
    :param title_key: 表头首格的多语言键。
    :param names: 模块名列表，为空时返回空片段，空态文案由调用方负责。
    :return: 消息元素列表。
    """
    if not names:
        return []
    prefix = msg.session_info.prefixes[0]
    columns = max(math.ceil(len(names) / MODULE_TABLE_MAX_ROWS), min(len(names), MODULE_TABLE_MIN_COLUMNS))
    title = msg.session_info.locale.t(title_key)

    # 表头与分隔行自带换行：表格的排版全由文本承载，不能交给适配器按元素换行
    parts = [Plain(f"| {title} |{' |' * (columns - 1)}\n|{'---|' * columns}\n| ", disable_joke=True)]
    for index, name in enumerate(names):
        parts.append(ActionText(f"{prefix}help {name}", show=name))
        if index + 1 == len(names):
            padding = (columns - (index + 1) % columns) % columns
            parts.append(Plain(" |" * (padding + 1) + "\n", disable_joke=True))
        elif (index + 1) % columns == 0:
            parts.append(Plain(" |\n| ", disable_joke=True))
        else:
            parts.append(Plain(" | ", disable_joke=True))
    return parts


def get_setup_button_data(msg: Bot.MessageSession) -> list[dict[str, str]]:
    """
    构造帮助菜单底部直达设置面板的按钮。

    按钮点击后经 interaction 事件另行建立会话，该会话的可用前缀取自全局配置，
    并不包含各平台在常规消息入口所用的前缀，故此处须使用 command_prefix。

    文案取自面板专设的按钮键，而非面板标题：后者带有分隔用的方括号，套进按钮里并不好看。

    :param msg: 消息会话。
    :return: 按钮数据；会话不具备按钮能力时为空列表。
    """
    if not msg.session_info.support_button:
        return []
    locale = msg.session_info.locale
    return arrange_buttons(
        [
            (locale.t("core.message.setup.list.button.target"), f"{command_prefix[0]}setup list target"),
            (locale.t("core.message.setup.list.button.sender"), f"{command_prefix[0]}setup list sender"),
        ]
    )


@hlp.command(
    "<module> [--legacy] {{I18N:core.help.help.detail}}", options_desc={"--legacy": "{I18N:help.option.legacy}"}
)
async def _(msg: Bot.MessageSession, module: str):
    is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
    is_superuser = msg.check_super_user()
    module_list = ModulesManager.return_modules_list(
        target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
    )
    alias = ModulesManager.modules_aliases

    if msg.parsed_msg:
        mdocs = []
        malias = []

        help_name = alias[module].split()[0] if module in alias else module.split()[0]
        if help_name in module_list:
            module_ = module_list[help_name]

            if not module_._db_load:
                await msg.finish(I18NContext("parser.module.unloaded", module=help_name))
            if module_.desc:
                desc = msg.session_info.locale.t_str(module_.desc)
                mdocs.append(desc)

            help_ = CommandParser(
                module_,
                msg=msg,
                module_name=module_.module_name,
                command_prefixes=msg.session_info.prefixes,
                is_superuser=is_superuser,
            )

            if help_.args:
                mdocs.append(help_.return_formatted_help_doc())

            regex_list = module_.regex_list.get(
                msg.session_info.target_from,
                show_required_superuser=is_superuser,
                show_required_base_superuser=is_base_superuser,
            )

            devs_msg = ""
            if (module_.required_superuser and not is_superuser) or (
                module_.required_base_superuser and not is_base_superuser
            ):
                pass
            elif module_.unsupported_reason(msg.session_info):
                pass
            else:
                if regex_list:
                    mdocs.append(str(I18NContext("core.help.regex.note")))
                    for regex in regex_list:
                        pattern = None
                        if isinstance(regex.pattern, str):
                            pattern = regex.pattern
                        elif isinstance(regex.pattern, re.Pattern):
                            pattern = regex.pattern.pattern
                        if pattern:
                            if msg.session_info.support_markdown:
                                pattern = re.sub(r"([\\`*_{}\[\]()#+\-.!>~|])", r"\\\1", pattern)
                            rdesc = regex.desc
                            if rdesc:
                                rdesc = msg.session_info.locale.t_str(rdesc)
                                mdocs.append(
                                    f"{pattern}{str(I18NContext('core.message.help.regex.detail', msg=rdesc))}"
                                )
                            else:
                                mdocs.append(f"{pattern}{str(I18NContext('core.message.help.regex.no_information'))}")

                if module_.alias:
                    for a in module_.alias:
                        malias.append(f"{a} -> {module_.alias[a]}")
                if module_.developers and not module_.base:
                    devs_msg = str(I18NContext("core.help.author")) + "{I18N:message.delimiter}".join(
                        module_.developers
                    )
                else:
                    devs_msg = ""

            if module_.doc:
                if help_page_url := CoreConfig.help_page_url:
                    wiki_msg = I18NContext(
                        "core.message.help.helpdoc.address",
                        url=MessageChain.assign(Url(help_page_url.replace("${module}", help_name))),
                    )

                elif help_url:
                    wiki_msg = I18NContext(
                        "core.message.help.helpdoc.address", url=MessageChain.assign(Url(help_url + help_name))
                    )

                else:
                    wiki_msg = ""
            else:
                wiki_msg = ""

            if (
                not msg.parsed_msg.get("--legacy", False)
                and msg.session_info.support_image
                and Bot.Info.web_render_status
            ):
                if (module_.required_superuser and not is_superuser) or (
                    module_.required_base_superuser and not is_base_superuser
                ):
                    pass
                elif module_.unsupported_reason(msg.session_info):
                    pass
                elif any(
                    (module_.alias, module_.desc, module_.developers, help_.return_formatted_help_doc(), regex_list)
                ):
                    try:
                        html_content = await env.get_template("help_doc.html").render_async(
                            locale=msg.session_info.locale,
                            module=module_,
                            help=help_,
                            help_name=help_name,
                            regex_list=regex_list,
                            escape=escape,
                            isinstance=isinstance,
                            str=str,
                            repattern=re.Pattern,
                            use_font_mirror=use_font_mirror,
                        )

                        # fname = f"{random_cache_path()}.html"
                        # with open(fname, "w", encoding="utf-8") as fi:
                        #     fi.write(html_content)

                        images = await web_render.element_screenshot(
                            ElementScreenshotOptions(content=html_content, element=[".botbox"])
                        )

                        cb: list[ImageElement] = cb64imglst(images, bot_img=True)

                        msgchain = MessageChain.assign(cb)
                        if wiki_msg:
                            msgchain.append(wiki_msg)
                        await msg.finish(msgchain)
                    except Exception:
                        Logger.exception()

                if wiki_msg:
                    await msg.finish(wiki_msg)
                else:
                    await msg.finish(I18NContext("core.help.info.none"))

            doc_msg = mdocs + [devs_msg, wiki_msg]
            if doc_msg:
                await msg.finish(doc_msg)
            else:
                await msg.finish(I18NContext("core.help.info.none"))
        else:
            await msg.finish(I18NContext("core.message.help.not_found"))


@hlp.command("[--legacy] {{I18N:core.help.help}}", options_desc={"--legacy": "{I18N:help.option.legacy}"})
async def _(msg: Bot.MessageSession):
    # 具备指令操作能力时，文字版的模块名可以点击直达详情，其价值高于图片排版，
    # 故优先于图片版。显式要求 --legacy 者仍得到最朴素的那一版。
    # 同时支持 markdown 的平台再进一步排成宽表：模块数增长由列数吸收，消息高度大体恒定。
    use_table = not msg.parsed_msg and msg.session_info.support_markdown and msg.session_info.support_action_text
    use_clickable = not use_table and not msg.parsed_msg and msg.session_info.support_action_text

    legacy_help = True
    if not use_clickable and not use_table and not msg.parsed_msg and msg.session_info.support_image:
        imgs = await help_generator(msg)
        if imgs:
            legacy_help = False

            help_msg_list = MessageChain.assign(
                I18NContext(
                    "core.message.help.all_modules",
                    prefix=msg.session_info.prefixes[0],
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}module list"),
                )
            )
            if help_url:
                help_msg_list.append(I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url))))
            if donate_url:
                help_msg_list.append(I18NContext("core.message.help.donate", url=MessageChain.assign(Url(donate_url))))
            await msg.finish(imgs + help_msg_list, button_data=get_setup_button_data(msg))
    if legacy_help:
        is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
        is_superuser = msg.check_super_user()
        module_list = ModulesManager.return_modules_list(
            target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
        )
        target_enabled_list = msg.session_info.enabled_modules

        essential = []
        module_ = []

        for key, value in module_list.items():
            if key[0] == "_":
                continue
            if not value._db_load and not value.base:
                continue
            if value.hidden:
                continue
            if value.unsupported_reason(msg.session_info):
                continue
            if not is_superuser and value.required_superuser or not is_base_superuser and value.required_base_superuser:
                continue

            if value.base:
                essential.append(key)
            else:
                module_.append(key)
        module_ = [m for m in module_ if m in target_enabled_list]

        if use_table:
            # 表格以纯文本收尾，其后的提示语不会被并入，无须 end_inline_run()
            help_msg = MessageChain.assign(
                build_module_table(msg, "core.message.help.table.base", essential)
                + build_module_table(msg, "core.message.help.table.external", module_)
            )
        elif use_clickable:
            help_msg = MessageChain.assign(
                build_clickable_modules(
                    msg,
                    [
                        ("core.message.help.legacy.base", essential),
                        ("core.message.help.legacy.external", module_),
                    ],
                )
            )
            end_inline_run(help_msg)
        else:
            help_msg = MessageChain.assign(I18NContext("core.message.help.legacy.base"))
            help_msg.append(Plain(" | ".join(essential), disable_joke=True))
            if module_:
                help_msg.append(I18NContext("core.message.help.legacy.external"))
                help_msg.append(Plain(" | ".join(module_), disable_joke=True))
        help_msg.append(
            I18NContext(
                "core.message.help.detail",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
            )
        )
        help_msg.append(
            I18NContext(
                "core.message.help.all_modules",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}module list"),
            )
        )
        if help_url:
            help_msg.append(I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url))))
        if donate_url:
            help_msg.append(I18NContext("core.message.help.donate", url=MessageChain.assign(Url(donate_url))))
        await msg.finish(help_msg, button_data=get_setup_button_data(msg))


async def modules_list_help(msg: Bot.MessageSession, legacy):
    # 与 ~help 同理：可点击的模块名优先于图片排版
    use_clickable = not legacy and msg.session_info.support_action_text

    legacy_help = True
    if not use_clickable and msg.session_info.support_image and not legacy:
        imgs = await help_generator(msg, show_disabled_modules=True, show_base_modules=False, show_dev_modules=False)
        if imgs:
            legacy_help = False
            help_msg = MessageChain.assign()
            if help_url:
                help_msg.append(I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url))))
            await msg.finish(imgs + help_msg)
    if legacy_help:
        module_list = ModulesManager.return_modules_list(
            target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
        )
        module_ = []
        for x in module_list:
            if x[0] == "_":
                continue
            if (
                module_list[x].base
                or module_list[x].hidden
                or not module_list[x]._db_load
                or module_list[x].required_superuser
                or module_list[x].required_base_superuser
            ):
                continue
            module_.append(module_list[x].module_name)
        if not module_:
            help_msg = MessageChain.assign(I18NContext("core.message.help.legacy.availables.none"))
        elif use_clickable:
            help_msg = MessageChain.assign(
                build_clickable_modules(msg, [("core.message.help.legacy.availables", module_)])
            )
            end_inline_run(help_msg)
        else:
            help_msg = MessageChain.assign(
                [I18NContext("core.message.help.legacy.availables"), Plain(" | ".join(module_), disable_joke=True)]
            )
        help_msg.append(
            I18NContext(
                "core.message.help.detail",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}help "),
            )
        )
        if help_url:
            help_msg.append(I18NContext("core.message.help.document", url=MessageChain.assign(Url(help_url))))
        await msg.finish(help_msg)


async def help_generator(
    msg: Bot.MessageSession,
    show_base_modules: bool = True,
    show_disabled_modules: bool = False,
    show_dev_modules: bool = True,
):
    is_base_superuser = msg.session_info.sender_id in Bot.base_superuser_list
    is_superuser = msg.check_super_user()
    module_list = ModulesManager.return_modules_list(
        target_from=msg.session_info.target_from, client_name=msg.session_info.client_name
    )
    target_enabled_list = msg.session_info.enabled_modules

    dev_module_list = []
    essential = {}
    module_ = {}

    for key, value in module_list.items():
        if key[0] == "_":
            continue
        if not value._db_load and not value.base:
            continue
        if value.hidden:
            continue
        if value.unsupported_reason(msg.session_info):
            continue
        if not is_superuser and value.required_superuser or not is_base_superuser and value.required_base_superuser:
            continue

        if value.base:
            essential[key] = value
        else:
            module_[key] = value

        if value.required_superuser or value.required_base_superuser:
            dev_module_list.append(key)

    if not show_disabled_modules:
        module_ = {k: v for k, v in module_.items() if k in target_enabled_list or k in dev_module_list}

    if show_base_modules:
        module_list = {**essential, **module_}
    else:
        module_list = module_

    if not show_dev_modules:
        module_list = {k: v for k, v in module_.items() if k not in dev_module_list}

    html_content = await env.get_template("module_list.html").render_async(
        msg=msg,
        locale=msg.session_info.locale,
        CommandParser=CommandParser,
        is_base_superuser=is_base_superuser,
        is_superuser=is_superuser,
        len=len,
        module_list=module_list,
        show_disabled_modules=show_disabled_modules,
        target_enabled_list=target_enabled_list,
        use_font_mirror=use_font_mirror,
    )
    fname = f"{random_cache_path()}.html"
    with open(fname, "w", encoding="utf-8") as fi:
        fi.write(html_content)

    images = await web_render.element_screenshot(ElementScreenshotOptions(content=html_content, element=[".botbox"]))
    if images:
        return cb64imglst(images, bot_img=True)
    return None
