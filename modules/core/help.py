import base64
import re
from io import BytesIO
import traceback
from typing import Dict, List, Optional

import aiohttp
import orjson as json
from PIL import Image as PILImage

from config import Config, CFG
from core.builtins import Bot, I18NContext, Image, Plain
from core.component import module
from core.loader import ModulesManager, current_unloaded_modules, err_modules
from core.logger import Logger
from core.parser.command import CommandParser
from core.types import Module
from core.utils.cache import random_cache_path
from core.utils.http import download
from core.utils.image_table import ImageTable, image_table_render
from core.utils.web_render import WebRender, webrender


hlp = module('help', base=True, doc=True)


@hlp.command('<module> [--legacy] {{core.help.help.detail}}',
             options_desc={'--legacy': '{help.option.legacy}'})
async def bot_help(msg: Bot.MessageSession, module: str):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    alias = ModulesManager.modules_aliases
    if msg.parsed_msg:
        msgs = []
        if module in alias:
            help_name = alias[module].split()[0]
        else:
            help_name = module.split()[0]
        if help_name in current_unloaded_modules:
            await msg.finish(msg.locale.t("parser.module.unloaded", module=help_name))
        elif help_name in err_modules:
            await msg.finish(msg.locale.t("error.module.unloaded", module=help_name))
        elif help_name in module_list:
            module_ = module_list[help_name]
            if module_.desc:
                desc = module_.desc
                if locale_str := re.match(r'\{(.*)}', desc):
                    if locale_str:
                        desc = msg.locale.t(locale_str.group(1))
                msgs.append(desc)
            help_ = CommandParser(module_list[help_name], msg=msg, bind_prefix=module_list[help_name].bind_prefix,
                                  command_prefixes=msg.prefixes)
            if help_.args:
                msgs.append(help_.return_formatted_help_doc())

            doc = '\n'.join(msgs)
            if module_.regex_list.set:
                doc += '\n' + msg.locale.t("core.message.help.support_regex")
                for regex in module_.regex_list.set:
                    pattern = None
                    if isinstance(regex.pattern, str):
                        pattern = regex.pattern
                    elif isinstance(regex.pattern, re.Pattern):
                        pattern = regex.pattern.pattern
                    if pattern:
                        desc = regex.desc
                        if desc:
                            doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.detail",
                                                                  msg=msg.locale.t_str(desc))
                        else:
                            doc += f'\n{pattern} ' + msg.locale.t("core.message.help.regex.no_information")
            module_alias = module_.alias
            malias = []
            if module_alias:
                for a in module_alias:
                    malias.append(f'{a} -> {module_alias[a]}')
            if module_.developers:
                devs = msg.locale.t('message.delimiter').join(module_.developers)
                devs_msg = '\n' + msg.locale.t("core.message.help.author.type1") + devs
            else:
                devs_msg = ''
            wiki_msg = ''
            if module_.doc:
                if Config('help_page_url', cfg_type=str):
                    wiki_msg = '\n' + msg.locale.t("core.message.help.helpdoc.address",
                                                   url=Config('help_page_url', cfg_type=str).replace('${module}', help_name))
                elif Config('help_url', cfg_type=str):
                    wiki_msg = '\n' + msg.locale.t("core.message.help.helpdoc.address",
                                                   url=(CFG.get_url('help_url') + help_name))
            if len(doc) > 500 and not msg.parsed_msg.get('--legacy', False) and msg.Feature.image:
                try:
                    tables = [ImageTable([[doc, '\n'.join(malias), devs]],
                                         [msg.locale.t("core.message.help.table.header.help"),
                                          msg.locale.t("core.message.help.table.header.alias"),
                                          msg.locale.t("core.message.help.author.type2")])]
                    imgs = await image_table_render(tables)
                    if imgs:
                        img_list = []
                        for img in imgs:
                            img_list.append(Image(img))
                        await msg.finish(img_list + [Plain(wiki_msg)])
                except Exception:
                    Logger.error(traceback.format_exc())
            if malias:
                doc += f'\n{msg.locale.t("core.help.alias")}\n' + '\n'.join(malias)
            doc_msg = (doc + devs_msg + wiki_msg).lstrip()
            if doc_msg != '':
                await msg.finish(doc_msg)
            else:
                await msg.finish(msg.locale.t("core.help.none"))
        else:
            await msg.finish(msg.locale.t("core.message.help.not_found"))


@hlp.command()
@hlp.command('[--legacy] {{core.help.help}}',
             options_desc={'--legacy': '{help.option.legacy}'})
async def _(msg: Bot.MessageSession):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    target_enabled_list = msg.enabled_modules
    legacy_help = True
    if not msg.parsed_msg and msg.Feature.image:
        imgs = await help_generater(msg, module_list, target_enabled_list)
        if imgs:
            legacy_help = False
            imgchain = []
            for img in imgs:
                imgchain.append(Image(img))

            help_msg_list = [I18NContext("core.message.help.more_information",
                                                    prefix=msg.prefixes[0])]
            if Config('help_url', cfg_type=str):
                help_msg_list.append(I18NContext("core.message.help.more_information.document",
                                                 url=Config('help_url', cfg_type=str)))
            if Config('donate_url', cfg_type=str):
                help_msg_list.append(I18NContext("core.message.help.more_information.donate",
                                                 url=Config('donate_url', cfg_type=str)))
            await msg.finish(imgchain + help_msg_list)
    if legacy_help:
        help_msg = [msg.locale.t("core.message.help.legacy.base")]
        essential = []
        for x in module_list:
            if module_list[x].base and not (
                    module_list[x].hidden or module_list[x].required_superuser or module_list[x].required_base_superuser):
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        module_ = []
        for x in module_list:
            if x in target_enabled_list and not (
                    module_list[x].hidden or module_list[x].required_superuser or module_list[x].required_base_superuser):
                module_.append(x)
        if module_:
            help_msg.append(msg.locale.t("core.message.help.legacy.external"))
            help_msg.append(' | '.join(module_))
        help_msg.append(
            msg.locale.t(
                "core.message.help.legacy.more_information",
                prefix=msg.prefixes[0]))
        if Config('help_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.document",
                    url=Config('help_url', cfg_type=str)))
        if Config('donate_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.donate",
                    url=Config('donate_url', cfg_type=str)))
        await msg.finish(help_msg)


async def modules_list_help(msg: Bot.MessageSession, legacy):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    target_enabled_list = msg.enabled_modules
    legacy_help = True
    if msg.Feature.image and not legacy:
        imgs = await help_generater(msg, module_list, target_enabled_list, show_disabled_module=True)
        if imgs:
            legacy_help = False
            imgchain = []
            for img in imgs:
                imgchain.append(Image(img))

            help_msg = [I18NContext("core.message.module.list.prompt", prefix=msg.prefixes[0])]
            if Config('help_url', cfg_type=str):
                help_msg.append(I18NContext(
                    "core.message.help.more_information.document",
                                url=Config('help_url', cfg_type=str)))
            await msg.finish(imgchain + help_msg)
    if legacy_help:
        module_ = []
        for x in module_list:
            if x[0] == '_':
                continue
            if module_list[x].base or module_list[x].hidden or \
                    module_list[x].required_superuser or module_list[x].required_base_superuser:
                continue
            module_.append(module_list[x].bind_prefix)
        if module_:
            help_msg = [msg.locale.t("core.message.help.legacy.availables")]
            help_msg.append(' | '.join(module_))
        else:
            help_msg = [msg.locale.t("core.message.help.legacy.availables.none")]
        help_msg.append(
            msg.locale.t(
                "core.message.module.list.prompt",
                prefix=msg.prefixes[0]))
        if Config('help_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.more_information.document",
                    url=Config('help_url', cfg_type=str)))
        await msg.finish(help_msg)


async def help_generater(msg: Bot.MessageSession, module_list: Dict[str, Module], target_enabled_list: Optional[List[str]] = [], show_all_modules: bool = False, show_disabled_module: bool = False, use_local=True):
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False
    if show_all_modules:
        show_disabled_module = True

    html_content ='''<!DOCTYPE html>
    <html lang="en">
    <head>
        <style>
            .grid-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, 100px);
                gap: 10px;
                padding: 10px;
            }
            .grid-item {
                position: relative;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 3px;
                border-radius: 15px;
                border: 1px solid #ccc;
                height: 100px;
                width: 80px;
                text-align: center;
                overflow: hidden;
                justify-content: center;
                font-size: 12px;
                margin: 5px 0;
                word-wrap: break-word;
                word-break: break-all;
                white-space: normal;
                background-color: transparent;
            }
            .orange { background-color: #F4B084; }
            .blue { background-color: #BDD7EE; }
            .grey { background-color: #A6A6A6; }
            .red { color: red; }
            .command-name {
                font-family: 'Courier New', Courier, monospace;
                font-size: 14px;
            }
            h1 {
                text-align: center;
                margin: 10px 0;
            }
            hr {
                border: 0;
                border-top: 1px dashed #ccc;
                margin: 5px 0;
            }
            .footer {
                text-align: left;
                font-size: 16px;
                white-space: pre-line;
                padding-left: 10px;
                line-height: 1;
            }
        </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK&family=Noto+Sans+JP&family=Noto+Sans+KR&family=Noto+Sans+SC&family=Noto+Sans+TC&display=swap" rel="stylesheet">
    <style>html body {
        margin-top: 0px !important;
        font-family: 'Noto Sans SC', sans-serif;
    }

    :lang(ko) {
        font-family: 'Noto Sans KR', 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', sans-serif;
    }

    :lang(ja) {
        font-family: 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-TW) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-HK) {
        font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
    }

    :lang(zh-Hans), :lang(zh-CN), :lang(zh) {
        font-family:  'Noto Sans SC', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans KR', sans-serif;
    }</style>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Module Help</title>
    </head>
    <body>
    <div class="botbox">
        <h1>模块命令列表</h1>
        <hr>
        <div class="grid-container">
    '''

    Logger.warning(str(module_list))
    for key, value in module_list.items():
        if value.hidden or value.required_superuser or value.required_base_superuser:
            continue
        if not show_disabled_module and key not in target_enabled_list and not value.base:
            continue

        command_count = len(value.command_list.set)
        regex_count = len(value.regex_list.set)

        top_bottom_class = "orange" if value.base else "blue"
        text_class = "red" if value.required_admin else ""

        if not show_all_modules and key not in target_enabled_list and not value.base:
            top_bottom_class = "grey"

        command_line = f'<div>{command_count} 条命令</div>' if command_count > 0 else ''
        regex_line = f'<div>{regex_count} 条表达式</div>' if regex_count > 0 else ''

        html_content += f'''
        <div class="grid-item {top_bottom_class}">
            <div class="{text_class}">
                <div class="command-name">{value.bind_prefix}</div>
                {command_line if command_count > 0 else ''}
                {regex_line if regex_count > 0 else ''}
            </div>
        </div>
    '''

    html_content += '''
        </div>
        <hr>
        <div class="footer">
            橙色为基础模块，蓝色为扩展模块，灰色为未启用模块。红色字的模块仅由管理员使用。<br>
            使用“~help &lt;模块&gt;”查看详细帮助。<br>
        </div>
    </div>
    </body>
    </html>
    '''
    fname = random_cache_path() + '.html'
    with open(fname, 'w', encoding='utf-8') as fi:
      fi.write(html_content)

    d = {'content': html_content, 'element': '.botbox'}

    html_ = json.dumps(d)

    try:
        pic = await download(webrender('element_screenshot', use_local=use_local),
                             status_code=200,
                             headers={'Content-Type': 'application/json'},
                             method="POST",
                             post_data=html_,
                             attempt=1,
                             timeout=30,
                             request_private_ip=True
                             )
    except aiohttp.ClientConnectorError:
        if use_local:
            pic = await download(webrender('element_screenshot', use_local=False),
                                 status_code=200,
                                 method='POST',
                                 headers={'Content-Type': 'application/json'},
                                 post_data=html_,
                                 request_private_ip=True
                                 )
        else:
            Logger.info('[Webrender] Generation Failed.')
            return False
    read = open(pic)
    load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)
    return img_lst