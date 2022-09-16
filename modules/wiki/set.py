import ujson as json

from core.builtins.message import MessageSession
from core.elements import Plain, Image, Url
from core.utils.image_table import image_table_render, ImageTable
from modules.wiki.utils.dbutils import WikiTargetInfo
from modules.wiki.utils.wikilib import WikiLib
from .wiki import wiki


@wiki.handle('set <WikiUrl> {设置起始查询Wiki}', required_admin=True)
async def set_start_wiki(msg: MessageSession):
    target = WikiTargetInfo(msg)
    check = await WikiLib(msg.parsed_msg['<WikiUrl>'], headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = WikiTargetInfo(msg).add_start_wiki(check.value.api)
            if result:
                await msg.finish(
                    f'成功添加起始Wiki：{check.value.name}' + ('\n' + check.message if check.message != '' else ''))
        else:
            await msg.finish(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (add|set) <Interwiki> <WikiUrl> {添加自定义Interwiki}', required_admin=True)
async def _(msg: MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    url = msg.parsed_msg['<WikiUrl>']
    target = WikiTargetInfo(msg)
    check = await WikiLib(url, headers=target.get_headers()).check_wiki_available()
    if check.available:
        if not check.value.in_blocklist or check.value.in_allowlist:
            result = target.config_interwikis(iw, check.value.api, let_it=True)
            if result:
                await msg.finish(f'成功：添加自定义Interwiki\n{iw} -> {check.value.name}')
        else:
            await msg.finish(f'错误：{check.value.name}处于黑名单中。')
    else:
        result = '错误：无法添加此Wiki。' + \
                 ('\n详细信息：' + check.message if check.message != '' else '')
        await msg.finish(result)


@wiki.handle('iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}', required_admin=True)
async def _(msg: MessageSession):
    iw = msg.parsed_msg['<Interwiki>']
    target = WikiTargetInfo(msg)
    result = target.config_interwikis(iw, let_it=False)
    if result:
        await msg.finish(f'成功：删除自定义Interwiki“{msg.parsed_msg["<Interwiki>"]}”')


@wiki.handle(['iw list {展示当前设置的Interwiki}', 'iw show {iw list的别名}',
              'iw (list|show) legacy {展示当前设置的Interwiki（旧版）}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    start_wiki = target.get_start_wiki()
    base_interwiki_link = None
    if start_wiki is not None:
        base_interwiki_link = await WikiLib(start_wiki, target.get_headers()).parse_page_info('Special:Interwiki')
        if base_interwiki_link.status:
            base_interwiki_link = base_interwiki_link.link
    base_interwiki_link_msg = f'\n此处展示的是为机器人设定的自定义Interwiki，如需查看起始wiki的Interwiki，请见：{str(Url(base_interwiki_link))}'
    if query != {}:
        if 'legacy' not in msg.parsed_msg and msg.Feature.image:
            columns = [[x, query[x]] for x in query]
            img = await image_table_render(ImageTable(columns, ['Interwiki', 'Url']))
        else:
            img = False
        if img:
            mt = f'使用{msg.prefixes[0]}wiki iw get <Interwiki> 可以获取interwiki对应的链接。'
            if base_interwiki_link is not None:
                mt += base_interwiki_link_msg
            await msg.finish([Image(img), Plain(mt)])
        else:
            result = '当前设置了以下Interwiki：\n' + \
                     '\n'.join([f'{x}: {query[x]}' for x in query])
            if base_interwiki_link is not None:
                result += base_interwiki_link_msg
            await msg.finish(result)
    else:
        await msg.finish('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle('iw get <Interwiki> {获取设置的Interwiki对应的api地址}')
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    query = target.get_interwikis()
    if query != {}:
        if msg.parsed_msg['<Interwiki>'] in query:
            await msg.finish(Url(query[msg.parsed_msg['<Interwiki>']]))
        else:
            await msg.finish(f'未找到Interwiki：{msg.parsed_msg["<Interwiki>"]}')
    else:
        await msg.finish('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


@wiki.handle(['headers show {展示当前设置的headers}', 'headers list {headers show 的别名}'])
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    prompt = f'当前设置了以下标头：\n{json.dumps(headers)}\n如需自定义，请使用~wiki headers set <headers>。\n' \
             f'格式：\n' \
             f'~wiki headers set {{"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"}}'
    await msg.finish(prompt)


@wiki.handle('headers (add|set) <Headers> {添加自定义headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    add = target.config_headers(
        " ".join(msg.trigger_msg.split(" ")[3:]), let_it=True)
    if add:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers (del|delete|remove|rm) <HeaderKey> {删除一个headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    delete = target.config_headers(
        [msg.parsed_msg['<HeaderHey>']], let_it=False)
    if delete:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('headers reset {重置headers}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    reset = target.config_headers('{}', let_it=None)
    if reset:
        await msg.finish(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@wiki.handle('prefix set <prefix> {设置查询自动添加前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    prefix = msg.parsed_msg['<prefix>']
    set_prefix = target.set_prefix(prefix)
    if set_prefix:
        await msg.finish(f'成功更新请求时所使用的前缀：{prefix}')


@wiki.handle('prefix reset {重置查询自动添加的前缀}', required_admin=True)
async def _(msg: MessageSession):
    target = WikiTargetInfo(msg)
    set_prefix = target.del_prefix()
    if set_prefix:
        await msg.finish(f'成功重置请求时所使用的前缀。')


@wiki.handle('fandom enable {禁用Fandom全局Interwiki查询}', 'fandom disable {禁用Fandom全局Interwiki查询}',
             required_admin=True)
async def _(msg: MessageSession):
    if msg.parsed_msg.get('enable', False):
        msg.data.edit_option('wiki_fandom_addon', True)
        await msg.finish('已启用Fandom全局Interwiki查询。')
    else:
        msg.data.edit_option('wiki_fandom_addon', False)
        await msg.finish('已禁用Fandom全局Interwiki查询。')
