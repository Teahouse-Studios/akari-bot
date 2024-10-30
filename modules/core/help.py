import base64
import re
from io import BytesIO
import traceback

import aiohttp
import orjson as json
from jinja2 import FileSystemLoader, Environment
from PIL import Image as PILImage

from core.config import Config, CFG
from core.builtins import Bot, I18NContext, Image, Plain, base_superuser_list
from core.component import module
from core.loader import ModulesManager, current_unloaded_modules, err_modules
from core.logger import Logger
from core.parser.command import CommandParser
from core.path import templates_path
from core.utils.cache import random_cache_path
from core.utils.http import download
from core.utils.image_table import ImageTable, image_table_render
from core.utils.web_render import WebRender, webrender


env = Environment(loader=FileSystemLoader(templates_path))


hlp = module('help', base=True, doc=True)


@hlp.command('<module> [--legacy] {{core.help.help.detail}}',
             options_desc={'--legacy': '{help.option.legacy}'})
async def bot_help(msg: Bot.MessageSession, module: str):
    is_base_superuser = msg.target.sender_id in base_superuser_list
    is_superuser = msg.check_super_user()
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
            if not module_.required_superuser and not module_.required_base_superuser or \
                    is_superuser and module_.required_superuser or \
                    is_base_superuser and module_.required_base_superuser:
                if module_.desc:
                    desc = msg.locale.t_str(module_.desc)
                    msgs.append(desc)
                help_ = CommandParser(module_list[help_name], msg=msg, bind_prefix=module_list[help_name].bind_prefix,
                                      command_prefixes=msg.prefixes, is_superuser=is_superuser)
                if help_.args:
                    msgs.append(help_.return_formatted_help_doc())

                doc = '\n'.join(msgs)
                if module_.regex_list.set:
                    doc += '\n' + msg.locale.t("core.message.help.support_regex")
                    regex_list = module_.regex_list.get(
                        msg.target.target_from,
                        show_required_superuser=is_superuser,
                        show_required_base_superuser=is_base_superuser)
                    for regex in regex_list:
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
            else:
                doc = ''

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
    legacy_help = True
    if not msg.parsed_msg and msg.Feature.image:
        imgs = await help_generator(msg)
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
        is_base_superuser = msg.target.sender_id in base_superuser_list
        is_superuser = msg.check_super_user()
        module_list = ModulesManager.return_modules_list(
            target_from=msg.target.target_from)
        target_enabled_list = msg.enabled_modules
        help_msg = [msg.locale.t("core.message.help.legacy.base")]
        essential = []
        for x in module_list:
            if module_list[x].base and not module_list[x].hidden or \
                    not is_superuser and module_list[x].required_superuser or \
                    not is_base_superuser and module_list[x].required_base_superuser:
                essential.append(module_list[x].bind_prefix)
        help_msg.append(' | '.join(essential))
        module_ = []
        for x in module_list:
            if x in target_enabled_list and not module_list[x].hidden or \
                    not is_superuser and module_list[x].required_superuser or \
                    not is_base_superuser and module_list[x].required_base_superuser:
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
    legacy_help = True
    if msg.Feature.image and not legacy:
        imgs = await help_generator(msg, show_disabled_modules=True, show_base_modules=False, show_dev_modules=False)
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
        module_list = ModulesManager.return_modules_list(
            target_from=msg.target.target_from)
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


async def help_generator(msg: Bot.MessageSession,
                         show_base_modules: bool = True,
                         show_disabled_modules: bool = False,
                         show_dev_modules: bool = True,
                         use_local: bool = True):
    is_base_superuser = msg.target.sender_id in base_superuser_list
    is_superuser = msg.check_super_user()
    module_list = ModulesManager.return_modules_list(
        target_from=msg.target.target_from)
    target_enabled_list = msg.enabled_modules

    if not WebRender.status:
        return False
    elif not WebRender.local:
        use_local = False

    dev_module_list = []
    essential = {}
    module_ = {}

    for key, value in module_list.items():
        if value.hidden:
            continue
        elif not is_superuser and value.required_superuser or \
                not is_base_superuser and value.required_base_superuser:
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

    html_content = env.get_template('help_doc.html').render(
        CommandParser=CommandParser,
        is_base_superuser=is_base_superuser,
        is_superuser=is_superuser,
        len=len,
        module_list=module_list,
        msg=msg,
        show_disabled_modules=show_disabled_modules,
        target_enabled_list=target_enabled_list)
    fname = f'{random_cache_path()}.html'
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
    with open(pic) as read:
        load_img = json.loads(read.read())
    img_lst = []
    for x in load_img:
        b = base64.b64decode(x)
        bio = BytesIO(b)
        bimg = PILImage.open(bio)
        img_lst.append(bimg)
    return img_lst
