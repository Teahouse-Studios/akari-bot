import re

import ujson as json

from core.elements import MessageSession, Plain, Image, Voice, Option
from core.loader import ModulesManager
from core.decorator import on_command, on_regex
from core.utils import download_to_cache
from database import BotDBUtil
from modules.wiki.dbutils import WikiTargetInfo
from modules.wiki.wikilib import wikilib
from .getinfobox import get_infobox_pic


@on_command('wiki', help_doc=('~wiki <PageName> {搜索一个Wiki页面，若搜索random则随机一个页面。}',
                           '~wiki set <WikiUrl> {设置起始查询Wiki}',
                           '~wiki iw (add|set) <Interwiki> <WikiUrl> {添加自定义Interwiki}',
                           '~wiki iw (del|delete|remove|rm) <Interwiki> {删除自定义Interwiki}',
                           '~wiki iw list {展示当前设置的Interwiki}',
                           '~wiki headers (add|set) <Headers> {添加自定义headers}',
                           '~wiki headers (del|delete|remove|rm) <HeaderKey> {删除一个headers}',
                           '~wiki headers reset {重置headers}',
                           '~wiki headers show {展示当前设置的headers}'),
            alias={'wiki_start_site': 'wiki set'},
            recommend_modules='wiki_inline',
            developers=['OasisAkari'],
            allowed_none=False)
async def wiki_wrapper(msg: MessageSession):
    if msg.parsed_msg['set'] and not msg.parsed_msg['headers'] and not msg.parsed_msg['iw']:
        await set_start_wiki(msg)
    elif msg.parsed_msg['iw']:
        await interwiki(msg)
    elif msg.parsed_msg['headers']:
        await set_headers(msg)
    else:
        await wiki(msg)


async def wiki(msg: MessageSession):
    command = f'[[{" ".join(msg.trigger_msg.split(" ")[1:])}]]'
    await regex_proc(msg, command)


async def set_start_wiki(msg: MessageSession):
    if not await msg.checkPermission():
        return await msg.sendMessage('你没有使用该命令的权限，请联系管理员进行操作。')
    check = await wikilib().check_wiki_available(msg.parsed_msg['<WikiUrl>'])
    if check[0]:
        result = WikiTargetInfo(msg).add_start_wiki(check[0])
        if result:
            await msg.sendMessage(f'成功添加起始Wiki：{check[1]}')
    else:
        result = '错误：' + check[1]
        await msg.sendMessage(result)


async def interwiki(msg: MessageSession):
    if not await msg.checkPermission():
        return await msg.sendMessage('你没有使用该命令的权限，请联系管理员进行操作。')
    iw = msg.parsed_msg['<Interwiki>']
    url = msg.parsed_msg['<WikiUrl>']
    target = WikiTargetInfo(msg)
    if msg.parsed_msg['add'] or msg.parsed_msg['set']:
        check = await wikilib().check_wiki_available(url,
                                                     headers=target.get_headers())
        if check[0]:
            result = target.config_interwikis(iw, check[0], let_it=True)
            if result:
                await msg.sendMessage(f'成功：添加自定义Interwiki\n{iw} -> {check[1]}')
        else:
            result = '错误：' + check[1]
            await msg.sendMessage(result)
    elif msg.parsed_msg['del'] or msg.parsed_msg['delete'] or msg.parsed_msg['remove'] or msg.parsed_msg['rm']:
        result = target.config_interwikis(iw, let_it=False)
        if result:
            await msg.sendMessage(f'成功：删除自定义Interwiki“{msg.parsed_msg["<Interwiki>"]}”')
    elif msg.parsed_msg['list']:
        query = target.get_interwikis()
        if query:
            result = '当前设置了以下Interwiki：\n' + '\n'.join([f'{x}: {query[x]}' for x in query])
            await msg.sendMessage(result)
        else:
            await msg.sendMessage('当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')


async def set_headers(msg: MessageSession):
    if not await msg.checkPermission():
        return await msg.sendMessage('你没有使用该命令的权限，请联系管理员进行操作。')
    target = WikiTargetInfo(msg)
    if msg.parsed_msg['show']:
        headers = target.get_headers()
        prompt = f'当前设置了以下标头：\n{json.dumps(headers)}\n如需自定义，请使用~wiki headers set <headers>。\n' \
                 f'格式：\n' \
                 f'~wiki headers set "{{"accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"}}"'
        await msg.sendMessage(prompt)
    elif msg.parsed_msg['add'] or msg.parsed_msg['set']:
        add = target.config_headers(msg.parsed_msg['<Headers>'], let_it=True)
        if add:
            await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')
    elif msg.parsed_msg['del'] or msg.parsed_msg['delete'] or msg.parsed_msg['remove'] or msg.parsed_msg['rm']:
        delete = target.config_headers([msg.parsed_msg['<HeaderHey>']], let_it=False)
        if delete:
            await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')
    elif msg.parsed_msg['reset']:
        reset = target.config_headers('', let_it=None)
        if reset:
            await msg.sendMessage(f'成功更新请求时所使用的Headers：\n{json.dumps(target.get_headers())}')


@on_regex('wiki_inline', pattern=r'\[\[.*?]]|{{.*?}}', mode='A',
          desc='解析消息中带有的[[]]或{{}}字符串自动查询Wiki，如[[海晶石]]',
          alias='wiki_regex', developers=['OasisAkari'])
async def regex_wiki(msg: MessageSession):
    await regex_proc(msg, msg.asDisplay())


ModulesManager.add_module(Option('wiki_fandom_addon', desc='为Fandom定制的查询附加功能。', developers=['OasisAkari']))


async def regex_proc(msg: MessageSession, display):
    mains = re.findall(r'\[\[(.*?)]]', display, re.I)
    templates = re.findall(r'{{(.*?)}}', display, re.I)
    find_dict = {}
    global_status = 'done'
    site_lock = False
    for main in mains:
        if main == '' or main in find_dict or main.find("{") != -1:
            pass
        else:
            if main[0] != '#':
                if main[0] == ':':
                    site_lock = True
                    find_dict.update({main[1:]: 'main'})
                else:
                    find_dict.update({main: 'main'})
    for template in templates:
        if template == '' or template in find_dict or template.find("{") != -1:
            pass
        else:
            if template[0] != '#':
                if template == ':':
                    site_lock = True
                    find_dict.update({template[1:]: 'template'})
                else:
                    find_dict.update({template: 'template'})
    if find_dict == {}:
        return
    waitlist = []
    imglist = []
    audlist = []
    urllist = {}
    msglist = []
    waitmsglist = []
    target = WikiTargetInfo(msg)
    headers = target.get_headers()
    for find in find_dict:
        if find_dict[find] == 'template':
            template = True
        else:
            template = False
        get_link = target.get_start_wiki()
        prompt = False
        if not get_link:
            prompt = '没有指定起始Wiki，已默认指定为中文Minecraft Wiki，可发送~wiki set <域名>来设定自定义起始Wiki。' \
                     '\n例子：~wiki set https://minecraft.fandom.com/zh/wiki/'
            get_link = 'https://minecraft.fandom.com/zh/api.php'
        iw = None
        matchinterwiki = re.match(r'(.*?):(.*)', find)
        if matchinterwiki and not site_lock:
            get_custom_iw = target.get_interwikis()
            if matchinterwiki.group(1) in get_custom_iw:
                get_link = get_custom_iw[matchinterwiki.group(1)]
                find = re.sub(matchinterwiki.group(1) + ':', '', find)
                iw = matchinterwiki.group(1)
            # fandom addon
            elif matchinterwiki.group(1) == 'w':
                if matchinterwiki := re.match(r'(.*?):(.*)', matchinterwiki.group(2)):
                    if matchinterwiki.group(1) == 'c':
                        if BotDBUtil.Module(msg).check_target_enabled_module('wiki_fandom_addon'):
                            if matchinterwiki := re.match(r'(.*?):(.*)', matchinterwiki.group(2)):
                                interwiki_split = matchinterwiki.group(1).split('.')
                                if len(interwiki_split) == 2:
                                    get_link = f'https://{interwiki_split[1]}.fandom.com/api.php'
                                    find = interwiki_split[0] + ':' + matchinterwiki.group(2)
                                    iw = 'w:c:' + interwiki_split[0]
                                else:
                                    get_link = f'https://{matchinterwiki.group(1)}.fandom.com/api.php'
                                    find = matchinterwiki.group(2)
                                    iw = 'w:c:' + matchinterwiki.group(1)
        if find == 'random':
            send_message = await wikilib().random_page(get_link, iw, headers)
        else:
            send_message = await wikilib().main(get_link, find, interwiki=iw,
                                                template=template,
                                                headers=headers)
        print(send_message)
        status = send_message['status']
        text = (prompt + '\n' if prompt else '') + send_message['text']
        if status == 'wait':
            global_status = 'wait'
            waitlist.append(send_message['title'])
            waitmsglist.append(Plain(('\n' if waitmsglist != [] else '') + text))
        if status == 'warn':
            global_status = 'warn'
            waitmsglist.append(Plain(('\n' if waitmsglist != [] else '') + text))
        if status == 'done':
            msglist.append(Plain(
                ('\n' if msglist != [] else '') + (
                    (send_message['url'] + ('\n' if text != '' else '')) if 'url' in send_message else '') + text))
            if 'net_image' in send_message:
                imglist.append(send_message['net_image'])
            if 'net_audio' in send_message:
                audlist.append(send_message['net_audio'])
            if 'apilink' in send_message:
                get_link = send_message['apilink']
            if 'url' in send_message:
                urllist.update({send_message['url']: get_link})
        if status is None:
            msglist.append(Plain('发生错误：机器人内部代码错误，请联系开发者解决。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title='))
    if msglist:
        await msg.sendMessage(msglist)
        if imglist and msg.Feature.image:
            imgchain = []
            for img in imglist:
                imgchain.append(Image(img))
            await msg.sendMessage(imgchain, quote=False)
        if audlist and msg.Feature.voice:
            for aud in audlist:
                await msg.sendMessage([Voice(path=await download_to_cache(aud))], quote=False)
    if urllist != {} and msg.Feature.image:
        print(urllist)
        infoboxchain = []
        for url in urllist:
            get_infobox = await get_infobox_pic(urllist[url], url, headers)
            if get_infobox:
                infoboxchain.append(Image(path=get_infobox))
        if infoboxchain:
            await msg.sendMessage(infoboxchain, quote=False)
    if global_status == 'warn':
        msg.target.senderInfo.edit('warns', int(msg.target.senderInfo.query.warns) + 1)
    if waitmsglist:
        wait = await msg.waitConfirm(waitmsglist)
        if wait:
            nwaitlist = []
            for waits in waitlist:
                waits1 = f'[[{waits}]]'
                nwaitlist.append(waits1)
            await regex_proc(msg, '\n'.join(nwaitlist))


"""async def query_page(msg: MessageSession, title: Union[str, list, tuple]):
    target = WikiTargetInfo(msg)
    for t in title:
        match_interwiki = re.match(r'(.*?):(.*)', t)

"""
