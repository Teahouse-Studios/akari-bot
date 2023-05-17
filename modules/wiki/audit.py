from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import Audit
from modules.wiki.utils.wikilib import WikiLib

aud = module('wiki_audit', alias='wa',
             developers=['Dianliang233', 'OasisAkari'], required_superuser=True)


@aud.handle(['trust <apiLink>', 'block <apiLink>'])
async def _(msg: Bot.MessageSession):
    req = msg.parsed_msg
    op = msg.session.sender
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('trust', False):
            res = Audit(api).add_to_AllowList(op)
            list_name = msg.locale.t('wiki.wiki_audit.list_name.allowlist')
        else:
            res = Audit(api).add_to_BlockList(op)
            list_name = msg.locale.t('wiki.wiki_audit.list_name.blocklist')
        if not res:
            await msg.finish(msg.locale.t('wiki.wiki_audit.add.message.failed', list_name=list_name) + api)
        else:
            await msg.finish(msg.locale.t('wiki.wiki_audit.add.message.success', list_name=list_name) + api)
    else:
        result = msg.locale.t('wiki.message.error.add') + \
            ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle(['distrust <apiLink>', 'unblock <apiLink>'])
async def _(msg: Bot.MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('distrust', False):
            res = Audit(api).remove_from_AllowList()
            if res is None:
                await msg.finish(msg.locale.t('wiki.wiki_audit.remove.message.failed.other') + api)
            list_name = msg.locale.t('wiki.wiki_audit.list_name.allowlist')
        else:
            res = Audit(api).remove_from_BlockList()
            list_name = msg.locale.t('wiki.wiki_audit.list_name.blocklist')
        if not res:
            await msg.finish(msg.locale.t('wiki.wiki_audit.remove.message.failed', list_name=list_name) + api)
        else:
            await msg.finish(msg.locale.t('wiki.wiki_audit.remove.message.success', list_name=list_name) + api)
    else:
        result = msg.locale.t('wiki.message.error.query') + \
            ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('query <apiLink>')
async def _(msg: Bot.MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        audit = Audit(api)
        allow = audit.inAllowList
        block = audit.inBlockList
        msg_list = []
        if allow:
            msg_list.append(api + msg.locale.t('wiki.wiki_audit.query.message.allowlist'))
        if block:
            msg_list.append(api + msg.locale.t('wiki.wiki_audit.query.message.blocklist'))
        if msg_list:
            msg_list.append(msg.locale.t('wiki.wiki_audit.query.message.conflict'))
            await msg.finish('\n'.join(msg_list))
        else:
            await msg.finish(api + msg.locale.t('wiki.wiki_audit.query.message.none'))
    else:
        result = msg.locale.t('wiki.message.error.query') + \
            ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('list')
async def _(msg: Bot.MessageSession):
    allow_list = Audit.get_allow_list()
    block_list = Audit.get_block_list()
    legacy = True
    if msg.Feature.image:
        send_msgs = []
        allow_columns = [[x[0], x[1]] for x in allow_list]
        if allow_columns:
            allow_table = ImageTable(data=allow_columns, headers=[
                msg.locale.t('wiki.wiki_audit.list.message.table.header.apilink'),
                msg.locale.t('wiki.wiki_audit.list.message.table.header.operator')
            ])
            if allow_table:
                allow_image = await image_table_render(allow_table)
                if allow_image:
                    send_msgs.append(Plain(msg.locale.t('wiki.wiki_audit.list.message.allowlist')))
                    send_msgs.append(Image(allow_image))
        block_columns = [[x[0], x[1]] for x in block_list]
        if block_columns:
            block_table = ImageTable(data=block_columns, headers=[
                msg.locale.t('wiki.wiki_audit.list.message.table.header.apilink'),
                msg.locale.t('wiki.wiki_audit.list.message.table.header.operator')
            ])
            if block_table:
                block_image = await image_table_render(block_table)
                if block_image:
                    send_msgs.append(Plain(msg.locale.t('wiki.wiki_audit.list.message.blocklist')))
                    send_msgs.append(Image(block_image))
        if send_msgs:
            await msg.finish(send_msgs)
            legacy = False
    if legacy:
        wikis = [msg.locale.t('wiki.wiki_audit.list.message.allowlist')]
        for al in allow_list:
            wikis.append(f'{al[0]} (by {al[1]})')
        wikis.append(msg.locale.t('wiki.wiki_audit.list.message.blocklist'))
        for bl in block_list:
            wikis.append(f'{bl[0]} (by {bl[1]})')
        await msg.finish('\n'.join(wikis))
