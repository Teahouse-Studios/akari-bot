from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Plain, Image
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import Audit
from modules.wiki.utils.wikilib import WikiLib

aud = on_command('wiki_audit', alias='wa',
                 developers=['Dianliang233', 'OasisAkari'], required_superuser=True)


@aud.handle(['trust <apiLink>', 'block <apiLink>'])
async def _(msg: MessageSession):
    req = msg.parsed_msg
    op = msg.session.sender
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('trust', False):
            res = Audit(api).add_to_AllowList(op)
            list_name = '白'
        else:
            res = Audit(api).add_to_BlockList(op)
            list_name = '黑'
        if not res:
            await msg.finish(f'失败，此wiki已经存在于{list_name}名单中：' + api)
        else:
            await msg.finish(f'成功加入{list_name}名单：' + api)
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle(['distrust <apiLink>', 'unblock <apiLink>'])
async def _(msg: MessageSession):
    req = msg.parsed_msg
    api = req['<apiLink>']
    check = await WikiLib(api).check_wiki_available()
    if check.available:
        api = check.value.api
        if req.get('distrust', False):
            res = Audit(api).remove_from_AllowList()
            list_name = '白'
        else:
            res = Audit(api).remove_from_BlockList()
            list_name = '黑'
        if not res:
            await msg.finish(f'失败，此wiki不存在于{list_name}名单中：' + api)
        else:
            await msg.finish(f'成功从{list_name}名单删除：' + api)
    else:
        result = '错误：无法查询此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('query <apiLink>')
async def _(msg: MessageSession):
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
            msg_list.append(api + '已存在于白名单。')
        if block:
            msg_list.append(api + '已存在于黑名单。')
        if msg_list:
            msg_list.append('优先级：白名单 > 黑名单')
            await msg.finish('\n'.join(msg_list))
        else:
            await msg.finish(api + '不存在于任何名单。')
    else:
        result = '错误：无法查询此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@aud.handle('list')
async def _(msg: MessageSession):
    allow_list = Audit.get_allow_list()
    block_list = Audit.get_block_list()
    legacy = True
    if msg.Feature.image:
        send_msgs = []
        allow_columns = [[x[0], x[1]] for x in allow_list]
        if allow_columns:
            allow_table = ImageTable(data=allow_columns, headers=[
                'APILink', 'Operator'])
            if allow_table:
                allow_image = await image_table_render(allow_table)
                if allow_image:
                    send_msgs.append(Plain('现有白名单：'))
                    send_msgs.append(Image(allow_image))
        block_columns = [[x[0], x[1]] for x in block_list]
        if block_columns:
            block_table = ImageTable(data=block_columns, headers=[
                'APILink', 'Operator'])
            if block_table:
                block_image = await image_table_render(block_table)
                if block_image:
                    send_msgs.append(Plain('现有黑名单：'))
                    send_msgs.append(Image(block_image))
        if send_msgs:
            await msg.finish(send_msgs)
            legacy = False
    if legacy:
        wikis = ['现有白名单：']
        for al in allow_list:
            wikis.append(f'{al[0]}（by {al[1]}）')
        wikis.append('现有黑名单：')
        for bl in block_list:
            wikis.append(f'{bl[0]}（by {bl[1]}）')
        await msg.finish('\n'.join(wikis))
