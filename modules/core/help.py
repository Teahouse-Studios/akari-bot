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

from jinja2 import FileSystemLoader, Environment

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
                devs_msg = '\n' + msg.locale.t("core.message.help.author") + devs
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
                                          msg.locale.t("core.message.help.table.header.author")])]
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
        imgs = await help_generator(msg, module_list, target_enabled_list)
        if imgs:
            legacy_help = False
            imgchain = []
            for img in imgs:
                imgchain.append(Image(img))

            help_msg_list = [I18NContext("core.message.help.all_modules",
                                         prefix=msg.prefixes[0])]
            if Config('help_url', cfg_type=str):
                help_msg_list.append(I18NContext("core.message.help.document",
                                                 url=Config('help_url', cfg_type=str)))
            if Config('donate_url', cfg_type=str):
                help_msg_list.append(I18NContext("core.message.help.donate",
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
                "core.message.help.detail",
                prefix=msg.prefixes[0]))
        help_msg.append(
            msg.locale.t(
                "core.message.help.all_modules",
                prefix=msg.prefixes[0]))
        if Config('help_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.document",
                    url=Config('help_url', cfg_type=str)))
        if Config('donate_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.donate",
                    url=Config('donate_url', cfg_type=str)))
        await msg.finish(help_msg)


async def modules_list_help(msg: Bot.MessageSession, legacy):
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    target_enabled_list = msg.enabled_modules
    legacy_help = True
    if msg.Feature.image and not legacy:
        imgs = await help_generator(msg, module_list, target_enabled_list, show_disabled_modules=True, show_base_modules=False)
        if imgs:
            legacy_help = False
            imgchain = []
            for img in imgs:
                imgchain.append(Image(img))

            help_msg = []
            if Config('help_url', cfg_type=str):
                help_msg.append(I18NContext(
                    "core.message.help.document",
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
                "core.message.help.detail",
                prefix=msg.prefixes[0]))
        if Config('help_url', cfg_type=str):
            help_msg.append(
                msg.locale.t(
                    "core.message.help.document",
                    url=Config('help_url', cfg_type=str)))
        await msg.finish(help_msg)


env = Environment(loader=FileSystemLoader('assets/templates'))


async def help_generator(msg: Bot.MessageSession, module_list: Dict[str, Module], target_enabled_list: Optional[List[str]] = [], show_base_modules: bool = True, show_disabled_modules: bool = False, use_local=True):
    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False
    essential = {}
    module_ = {}
    for key, value in module_list.items():
        if value.hidden or value.required_superuser or value.required_base_superuser:
            continue
        elif value.base:
            essential[key] = value
        else:
            module_[key] = value


    if not show_disabled_modules:
        module_ = {k: v for k, v in module_.items() if k in target_enabled_list}
    
    if show_base_modules:
        module_list = {**essential, **module_}
    else:
        module_list = module_

    html_content = env.get_template('help_doc.html').render(
        module_list=module_list,
        msg=msg,
        show_disabled_modules=show_disabled_modules,
        target_enabled_list=target_enabled_list,
        len=len,
        CommandParser=CommandParser)
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
