from datetime import datetime

from config import Config
from core.builtins import Bot, Plain, Image
from core.component import module
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import Audit
from modules.wiki.utils.wikilib import WikiLib


if Config('enable_urlmanager'):
    aud = module('wiki_audit', required_superuser=True,
             alias='wau')

    @aud.command(['trust <apilink>',
                  'block <apilink>'])
    async def _(msg: Bot.MessageSession, apilink: str):
        date = msg.ts2strftime(datetime.now().timestamp(), timezone=False)
        check = await WikiLib(apilink).check_wiki_available()
        if check.available:
            apilink = check.value.apilink
            if msg.parsed_msg.get('trust', False):
                res = Audit(apilink).add_to_AllowList(date)
                list_name = msg.locale.t('wiki.message.wiki_audit.list_name.allowlist')
            else:
                res = Audit(apilink).add_to_BlockList(date)
                list_name = msg.locale.t('wiki.message.wiki_audit.list_name.blocklist')
            if not res:
                await msg.finish(msg.locale.t('wiki.message.wiki_audit.add.failed', list_name=list_name, api=apilink))
            else:
                await msg.finish(msg.locale.t('wiki.message.wiki_audit.add.success', list_name=list_name) + apilink)
        else:
            result = msg.locale.t('wiki.message.error.add') + \
                ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
            await msg.finish(result)

    @aud.command(['distrust <apiLink>',
                  'unblock <apiLink>'])
    async def _(msg: Bot.MessageSession, apilink: str):
        if msg.parsed_msg.get('distrust', False):
            res = Audit(apilink).remove_from_AllowList()  # 已关闭的站点无法验证有效性
            if not res:
                await msg.finish(msg.locale.t('wiki.message.wiki_audit.remove.failed.other', api=apilink))
            list_name = msg.locale.t('wiki.message.wiki_audit.list_name.allowlist')
        else:
            res = Audit(apilink).remove_from_BlockList()
            list_name = msg.locale.t('wiki.message.wiki_audit.list_name.blocklist')
        if not res:
            await msg.finish(msg.locale.t('wiki.message.wiki_audit.remove.failed', list_name=list_name, api=apilink))
        else:
            await msg.finish(msg.locale.t('wiki.message.wiki_audit.remove.success', list_name=list_name) + apilink)

    @aud.command('query <apilink>')
    async def _(msg: Bot.MessageSession, apilink: str):
        check = await WikiLib(apilink).check_wiki_available()
        if check.available:
            apilink = check.value.apilink
            audit = Audit(apilink)
            msg_list = []
            if audit.inAllowList:
                msg_list.append(msg.locale.t('wiki.message.wiki_audit.query.allowlist', api=apilink))
            if audit.inBlockList:
                msg_list.append(msg.locale.t('wiki.message.wiki_audit.query.blocklist', api=apilink))
            if msg_list:
                msg_list.append(msg.locale.t('wiki.message.wiki_audit.query.conflict'))
                await msg.finish('\n'.join(msg_list))
            else:
                await msg.finish(msg.locale.t('wiki.message.wiki_audit.query.none', api=apilink))
        else:
            result = msg.locale.t('wiki.message.error.query') + \
                ('\n' + msg.locale.t('wiki.message.error.info') + check.message if check.message != '' else '')
            await msg.finish(result)

    @aud.command('list [legacy]')
    async def _(msg: Bot.MessageSession):
        allow_list = Audit.get_allow_list()
        block_list = Audit.get_block_list()
        legacy = True
        if not msg.parsed_msg.get('legacy', False) and msg.Feature.image:
            send_msgs = []
            allow_columns = [[x[0], x[1]] for x in allow_list]
            if allow_columns:
                allow_table = ImageTable(data=allow_columns, headers=[
                    msg.locale.t('wiki.message.wiki_audit.list.table.header.apilink'),
                    msg.locale.t('wiki.message.wiki_audit.list.table.header.date')
                ])
                if allow_table:
                    allow_image = await image_table_render(allow_table)
                    if allow_image:
                        send_msgs.append(Plain(msg.locale.t('wiki.message.wiki_audit.list.allowlist')))
                        send_msgs.append(Image(allow_image))
            block_columns = [[x[0], x[1]] for x in block_list]
            if block_columns:
                block_table = ImageTable(data=block_columns, headers=[
                    msg.locale.t('wiki.message.wiki_audit.list.table.header.apilink'),
                    msg.locale.t('wiki.message.wiki_audit.list.table.header.date')
                ])
                if block_table:
                    block_image = await image_table_render(block_table)
                    if block_image:
                        send_msgs.append(Plain(msg.locale.t('wiki.message.wiki_audit.list.blocklist')))
                        send_msgs.append(Image(block_image))
            if send_msgs:
                await msg.finish(send_msgs)
                legacy = False
        if legacy:
            wikis = [msg.locale.t('wiki.message.wiki_audit.list.allowlist')]
            for al in allow_list:
                wikis.append(f'{al[0]} ({al[1]})')
            wikis.append(msg.locale.t('wiki.message.wiki_audit.list.blocklist'))
            for bl in block_list:
                wikis.append(f'{bl[0]} ({bl[1]})')
            await msg.finish('\n'.join(wikis))
