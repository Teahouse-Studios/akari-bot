import ujson as json

from core.builtins import Bot, Plain, Image, Url
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.wikilib import WikiLib
from .wiki import wiki

from config import Config


@wiki.handle('set <WikiUrl> {{wiki.set.help}}', required_admin=True)
async def set_start_wiki(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    check = await WikiLib(msg.parsed_msg['<WikiUrl>'], headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = WikiTargetInfo(msg).add_start_wiki(check.value.api)
            if result:
                await msg.finish(
                    msg.locale.t("wiki.set.message.success", name=check.value.name) + ('\n' + check.message if check.message != '' else '') +
                    (('\n' + msg.locale.t("wiki.message.untrust") + Config("wiki_whitelist_url"))
                     if not check.value.in_allowlist else ''))
        else:
            await msg.finish(msg.locale.t("wiki.message.error.blocked", name=check.value.name))
    else:
        result = msg.locale.t('wiki.message.error.add') + \
                 ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (add|set) <Interwiki> <WikiUrl> {{wiki.iw.set.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    url = msg.parsed_msg['<WikiUrl>']
    target = WikiTargetInfo(msg)
    check = await WikiLib(url, headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = target.config_interwikis(iw, check.value.api, let_it=True)
            if result:
                await msg.finish(msg.locale.t("wiki.iw.set.message.success", iw=iw, name=check.value.name) +
                                 (('\n' + msg.locale.t("wiki.message.untrust") + Config("wiki_whitelist_url"))
                                  if not check.value.in_allowlist else ''))
        else:
            await msg.finish(msg.locale.t("wiki.message.error.blocked", name=check.value.name))
    else:
        result = msg.locale.t('wiki.message.error.add') + \
                 ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (del|delete|remove|rm) <Interwiki> {{wiki.iw.remove.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    target = WikiTargetInfo(msg)
    result = target.config_interwikis(iw, let_it=False)
    if result:
        await msg.finish(msg.locale.t("wiki.iw.remove.message.success", iw=iw))


@wiki.handle(['iw (list|show) {{wiki.iw.list.help}}',
              'iw (list|show) legacy {{wiki.iw.list.help.legacy}}'])
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    start_wiki = target.get_start_wiki()
    base_interwiki_link = None
    if start_wiki is not None:
        base_interwiki_link_ = await WikiLib(start_wiki, target.get_headers()).parse_page_info('Special:Interwiki')
        if base_interwiki_link_.status:
            base_interwiki_link = base_interwiki_link_.link
    if query != {}:
        if 'legacy' not in msg.parsed_msg and msg.Feature.image:
            columns = [[x, query[x]] for x in query]
            img = await image_table_render(ImageTable(columns, ['Interwiki', 'Url']))
        else:
            img = False
        if img:
            mt = msg.locale.t("wiki.iw.list.message", prefix=msg.prefixes[0])
            if base_interwiki_link is not None:
                mt += '\n' + msg.locale.t("wiki.iw.list.message.redirect", url=str(Url(base_interwiki_link)))
            await msg.finish([Image(img), Plain(mt)])
        else:
            result = msg.locale.t("wiki.iw.list.message.legacy") + '\n' + \
                     '\n'.join([f'{x}: {query[x]}' for x in query])
            if base_interwiki_link is not None:
                result += '\n' + msg.locale.t("wiki.iw.list.message.redirect", url=str(Url(base_interwiki_link)))
            await msg.finish(result)
    else:
        await msg.finish(msg.locale.t("wiki.iw.message.none", prefix=msg.prefixes[0]))


@wiki.handle('iw get <Interwiki> {{wiki.iw.get.help}}')
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    if query != {}:
        if msg.parsed_msg['<Interwiki>'] in query:
            await msg.finish(Url(query[msg.parsed_msg['<Interwiki>']]))
        else:
            await msg.finish(msg.locale.t("wiki.iw.get.message.not_found", iw=iw))
    else:
        await msg.finish(msg.locale.t("wiki.iw.message.none", prefix=msg.prefixes[0]))


@wiki.handle(['headers (list|show) {{wiki.headers.list.help}}'])
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    prompt = msg.locale.t("wiki.headers.list.message")
    await msg.finish(prompt)


@wiki.handle('headers (add|set) <Headers> {{wiki.headers.set.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    add = target.config_headers(
        " ".join(msg.trigger_msg.split(" ")[3:]), let_it=True)
    if add:
        await msg.finish(msg.locale.t("wiki.headers.set.message.success", headers=json.dumps(target.get_headers())))


@wiki.handle('headers (del|delete|remove|rm) <HeaderKey> {{wiki.headers.remove.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    delete = target.config_headers(
        [msg.parsed_msg['<HeaderHey>']], let_it=False)
    if delete:
        await msg.finish(msg.locale.t("wiki.headers.set.message.success", headers=json.dumps(target.get_headers())))


@wiki.handle('headers reset {{wiki.headers.reset.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    reset = target.config_headers('{}', let_it=None)
    if reset:
        await msg.finish(msg.locale.t("wiki.headers.reset.message.success"))


@wiki.handle('prefix set <prefix> {{wiki.prefix.set.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    prefix = msg.parsed_msg['<prefix>']
    set_prefix = target.set_prefix(prefix)
    if set_prefix:
        await msg.finish(msg.locale.t("wiki.prefix.set.message.success", wiki_prefix=prefix))


@wiki.handle('prefix reset {{wiki.prefix.reset.help}}', required_admin=True)
async def _(msg: Bot.MessageSession):
    target = WikiTargetInfo(msg)
    set_prefix = target.del_prefix()
    if set_prefix:
        await msg.finish(msg.locale.t("wiki.prefix.reset.message.success"))


@wiki.handle('fandom enable {{wiki.fandom.enable.help}}', 'fandom disable {{wiki.fandom.disable.help}}',
             required_admin=True)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get('enable', False):
        msg.data.edit_option('wiki_fandom_addon', True)
        await msg.finish(msg.locale.t("wiki.fandom.enable.message"))
    else:
        msg.data.edit_option('wiki_fandom_addon', False)
        await msg.finish(msg.locale.t("wiki.fandom.disable.message"))


@wiki.handle('redlink enable {{wiki.redlink.enable.help}}', 'redlink disable {{wiki.redlink.disable.help}}',
             required_admin=True)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get('enable', False):
        msg.data.edit_option('wiki_redlink', True)
        await msg.finish(msg.locale.t("wiki.redlink.enable.message"))
    else:
        msg.data.edit_option('wiki_redlink', False)
        await msg.finish(msg.locale.t("wiki.redlink.disable.message"))
