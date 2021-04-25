import re
import traceback

from graia.application import MessageChain
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Image, Voice
from graia.application.message.elements.internal import Plain

import modules.wiki.wikilib
from core.template import sendMessage, check_permission, wait_confirm, revokeMessage, Nudge, download_to_cache, \
    slk_converter
from core.elements import Target
from database import BotDB
from modules.wiki.database import WikiDB
from .getinfobox import get_infobox_pic


async def wiki_loader(kwargs: dict):
    kwargs['trigger_msg'] = cmd = re.sub(r'^wiki ', '', kwargs['trigger_msg'])
    cmd = cmd.split(' ')
    if isinstance(cmd, list):
        if len(cmd) > 1:
            if cmd[0] == 'set':
                kwargs['trigger_msg'] = cmd[1]
                await set_start_wiki(kwargs)
            elif cmd[0] == 'iw':
                kwargs['trigger_msg'] = ' '.join(cmd[1:])
                await interwiki(kwargs)
            elif cmd[0] == 'headers':
                kwargs['trigger_msg'] = ' '.join(cmd[1:])
                await set_headers(kwargs)
            else:
                await wiki_wrapper(kwargs)
        else:
            await wiki_wrapper(kwargs)
    else:
        await wiki_wrapper(kwargs)


async def wiki_wrapper(kwargs: dict):
    command = kwargs['trigger_msg']
    start_table = 'start_wiki_link_' + kwargs[Target].target_from
    headtable = 'request_headers_' + kwargs[Target].target_from
    triggerId = kwargs[Target].id
    headers = WikiDB.config_headers('get', headtable, triggerId)
    prompt = False
    get_link = WikiDB.get_start_wiki(start_table, triggerId)
    if not get_link:
        prompt = '没有指定起始Wiki，已默认指定为中文Minecraft Wiki，可发送~wiki set <域名>来设定自定义起始Wiki。' \
                 '\n例子：~wiki set https://minecraft-zh.gamepedia.com/'
        WikiDB.add_start_wiki(start_table, triggerId,
                              'https://minecraft-zh.gamepedia.com/api.php')
        get_link = 'https://minecraft-zh.gamepedia.com/api.php'
    iw = None
    co = False
    check_fandom_addon_enable = BotDB.check_enable_modules(kwargs,
                                                           'wiki_fandom_addon')
    if check_fandom_addon_enable:
        matchsite = re.match(r'\?(.*?) (.*)', command)
        if matchsite:
            get_link = 'https://' + matchsite.group(1) + '.fandom.com/api.php'
            iw = 'fd:' + matchsite.group(1)
            co = True
            command = matchsite.group(2)
        matchfd = re.match(r'^fd:(.*?):(.*)', command)
        if matchfd:
            get_link = 'https://' + matchfd.group(1) + '.fandom.com/api.php'
            iw = 'fd:' + matchfd.group(1)
            co = True
            command = matchsite.group(2)
        matchinterwiki = re.match(r'(.*?):(.*)', command)
        if matchinterwiki:
            if matchinterwiki.group(1) == 'w':
                matchinterwiki = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                if matchinterwiki:
                    if matchinterwiki.group(1) == 'c':
                        matchinterwiki = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                        if matchinterwiki:
                            interwiki_split = matchinterwiki.group(1).split('.')
                            if len(interwiki_split) == 2:
                                get_link = f'https://{interwiki_split[1]}.fandom.com/api.php'
                                command = interwiki_split[0] + ':' + matchinterwiki.group(2)
                                iw = interwiki_split[0]
                            else:
                                get_link = f'https://{matchinterwiki.group(1)}.fandom.com/api.php'
                                command = matchinterwiki.group(2)
                                iw = matchinterwiki.group(1)
                            co = True

    print(co)
    matchinterwiki = re.match(r'(.*?):(.*)', command)
    if matchinterwiki and not co:
        get_custom_iw = WikiDB.get_custom_interwiki('custom_interwiki_' + kwargs[Target].target_from, kwargs[Target].id,
                                                        matchinterwiki.group(1))
        if get_custom_iw:
            iw = matchinterwiki.group(1)
            get_link = get_custom_iw
            command = re.sub(matchinterwiki.group(1) + ':', '', command)
    if command == 'random':
        msg = await wikilib.wikilib().random_page(get_link, iw=iw, headers=headers)
    else:
        msg = await wikilib.wikilib().main(get_link, command, interwiki=iw, headers=headers)
    if msg['status'] == 'done':
        msgchain = MessageChain.create(
            [Plain((prompt + '\n' if prompt else '') + (msg['url'] + '\n' if 'url' in msg else '') + msg['text'])])
        if 'net_image' in msg:
            try:
                imgchain = MessageChain.create([Image.fromNetworkAddress(msg['net_image'])])
                msgchain = msgchain.plusWith(imgchain)
            except:
                pass
        await sendMessage(kwargs, msgchain)
        if 'apilink' in msg:
            get_link = msg['apilink']
        if 'url' in msg:
            pic = await get_infobox_pic(get_link, msg['url'], headers)
            imgchain = MessageChain.create([Image.fromLocalFile(pic)])
            await sendMessage(kwargs, imgchain)

    elif msg['status'] == 'wait':
        await sendMessage(kwargs, MessageChain.create([Plain(msg['text'])]))
        wait = await wait_confirm(kwargs)
        if wait:
            msg = await wikilib.wikilib().main(get_link, msg['title'])
            await sendMessage(kwargs, MessageChain.create([Plain((prompt + '\n' if prompt else '') + msg['title'])]))
    elif msg['status'] == 'warn':
        if Group in kwargs:
            trigger = kwargs[Member].id
        if Friend in kwargs:
            trigger = kwargs[Friend].id
        BotDB.warn_someone(trigger)
        await sendMessage(kwargs, MessageChain.create([Plain((prompt + '\n' if prompt else '') + msg['text'])]))


async def set_start_wiki(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub(r'^wiki_start_site ', '', command)
    if Group in kwargs:
        if not check_permission(kwargs):
            result = '你没有在群内使用该命令的权限，请联系管理员进行操作。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
            return
    check = await wikilib.wikilib().check_wiki_available(command)
    if check[0]:
        result = WikiDB.add_start_wiki('start_wiki_link_' + kwargs[Target].target_from, kwargs[Target].id, check[0])
        await sendMessage(kwargs, MessageChain.create([Plain(result + check[1])]))
    else:
        if check[1] == 'Timeout':
            result = '错误：尝试建立连接超时。'
        else:
            result = '错误：此站点也许不是一个有效的Mediawiki：' + check[1]
        link = re.match(r'^(https?://).*', command)
        if not link:
            result = '错误：所给的链接没有指明协议头（链接应以http://或https://开头）。'
        await sendMessage(kwargs, MessageChain.create([Plain(result)]))


async def interwiki(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub(r'^interwiki ', '', command)
    command = command.split(' ')
    print(command)
    if Group in kwargs:
        check = check_permission(kwargs)
        if not check:
            result = '你没有使用该命令的权限，请联系管理员进行操作。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
            return
    table = 'custom_interwiki_' + kwargs[Target].target_from
    target = kwargs[Target].id
    if command[0] == 'add':
        command = ' '.join(command[1:])
        command = re.sub(' ', '>', command)
        iw = command.split('>')
        if len(iw) == 1 or len(iw) > 2:
            await sendMessage(kwargs, '错误：命令不合法：~wiki iw add <interwiki> <url>')
            return
        check = await wikilib.wikilib().check_wiki_available(iw[1], headers=WikiDB.config_headers('get', table, target))
        if check[0]:
            result = WikiDB.config_custom_interwiki('add', table, target, iw[0],
                                                    check[0])
            await sendMessage(kwargs, MessageChain.create([Plain(result + f'{iw[0]} > {check[1]}')]))
        else:
            if check[1] == 'Timeout':
                result = '错误：尝试建立连接超时。'
            else:
                result = '错误：此站点也许不是一个有效的Mediawiki：' + check[1]
            link = re.match(r'^(https?://).*', iw[1])
            if not link:
                result = '错误：所给的链接没有指明协议头（链接应以http://或https://开头）。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
    elif command[0] == 'del':
        result = WikiDB.config_custom_interwiki('del', table, target, command[1])
        await sendMessage(kwargs, MessageChain.create([Plain(result)]))
    elif command[0] == 'list':
        query_database = WikiDB.get_custom_interwiki_list(table, target)
        if query_database:
            result = '当前设置了以下Interwiki：\n' + query_database
            await sendMessage(kwargs, result)
        else:
            await sendMessage(kwargs, '当前没有设置任何Interwiki，使用~wiki iw add <interwiki> <api_endpoint_link>添加一个。')
    else:
        await sendMessage(kwargs, '命令不合法，参数应为add/del/list。')


async def set_headers(kwargs: dict):
    command = kwargs['trigger_msg']
    command = command.split(' ')
    if Group in kwargs:
        check = check_permission(kwargs)
        if not check:
            result = '你没有使用该命令的权限，请联系管理员进行操作。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
            return
    table = 'request_headers_' + kwargs[Target].target_from
    id = kwargs[Target].id
    do = command[0]
    if do == 'show':
        headers = WikiDB.config_headers(do, table, id)
        msg = f'当前设置了以下标头：\n{headers}\n如需自定义，请使用~wiki headers <set> <headers>，不同标头之间使用换行隔开。'
    else:
        msg = WikiDB.config_headers(do, table, id, ' '.join(command[1:]))
    await sendMessage(kwargs, msg)


async def regex_wiki(kwargs: dict):
    display = kwargs[MessageChain].asDisplay()

    async def regex_proc(kwargs: dict, display):
        mains = re.findall(r'\[\[(.*?)\]\]', display, re.I)
        templates = re.findall(r'\{\{(.*?)\}\}', display, re.I)
        find_dict = {}
        global_status = 'done'
        for main in mains:
            if main == '' or main in find_dict or main.find("{") != -1:
                pass
            else:
                find_dict.update({main: 'main'})
        for template in templates:
            if template == '' or template in find_dict or template.find("{") != -1:
                pass
            else:
                find_dict.update({template: 'template'})
        if find_dict != {}:
            await Nudge(kwargs)
            waitlist = []
            imglist = []
            audlist = []
            urllist = {}
            msglist = MessageChain.create([])
            waitmsglist = MessageChain.create([])
            table = 'start_wiki_link_' + kwargs[Target].target_from
            target = kwargs[Target].id
            headtable = 'request_headers_' + kwargs[Target].target_from
            headers = WikiDB.config_headers('get', headtable, target)
            for find in find_dict:
                if find_dict[find] == 'template':
                    template = True
                else:
                    template = False
                get_link = WikiDB.get_start_wiki(table, target)
                prompt = False
                if not get_link:
                    prompt = '没有指定起始Wiki，已默认指定为中文Minecraft Wiki，可发送~wiki set <域名>来设定自定义起始Wiki。' \
                             '\n例子：~wiki set https://minecraft.fandom.com/zh/'
                    WikiDB.add_start_wiki(table, target,
                                          'https://minecraft.fandom.com/zh/api.php')
                    get_link = 'https://minecraft.fandom.com/zh/api.php'
                iw = None
                matchinterwiki = re.match(r'(.*?):(.*)', find)
                if matchinterwiki:
                    iw_table = 'custom_interwiki_' + kwargs[Target].target_from
                    get_custom_iw = modules.wiki.WikiDB.get_custom_interwiki(iw_table,
                                                                             target,
                                                                             matchinterwiki.group(1))
                    if get_custom_iw:
                        get_link = get_custom_iw
                        find = re.sub(matchinterwiki.group(1) + ':', '', find)
                        iw = matchinterwiki.group(1)
                    # fandom addon
                    if matchinterwiki.group(1) == 'w':
                        matchinterwiki = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                        if matchinterwiki:
                            if matchinterwiki.group(1) == 'c':
                                check_fandom_addon_enable = BotDB.check_enable_modules(kwargs[Target].id,
                                                                                       'wiki_fandom_addon')
                                if check_fandom_addon_enable:
                                    matchinterwiki = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                                    if matchinterwiki:
                                        interwiki_split = matchinterwiki.group(1).split('.')
                                        if len(interwiki_split) == 2:
                                            get_link = f'https://{interwiki_split[1]}.fandom.com/api.php'
                                            find = interwiki_split[0] + ':' + matchinterwiki.group(2)
                                            iw = interwiki_split[0]
                                        else:
                                            get_link = f'https://{matchinterwiki.group(1)}.fandom.com/api.php'
                                            find = matchinterwiki.group(2)
                                            iw = matchinterwiki.group(1)
                msg = await modules.wiki.wikilib.wikilib().main(get_link, find, interwiki=iw, template=template,
                                                                headers=headers)
                status = msg['status']
                text = (prompt + '\n' if prompt else '') + msg['text']
                if status == 'wait':
                    global_status = 'wait'
                    waitlist.append(msg['title'])
                    waitmsglist = waitmsglist.plusWith(MessageChain.create(
                        [Plain(('\n' if waitmsglist != MessageChain.create([]) else '') + text)]))
                if status == 'warn':
                    global_status = 'warn'
                    msglist = msglist.plusWith(MessageChain.create(
                        [Plain(('\n' if msglist != MessageChain.create([]) else '') + text)]))
                if status == 'done':
                    msglist = msglist.plusWith(MessageChain.create([Plain(
                        ('\n' if msglist != MessageChain.create([]) else '') + (
                            msg['url'] + '\n' if 'url' in msg else '') + text)]))
                    if 'net_image' in msg:
                        imglist.append(msg['net_image'])
                    if 'net_audio' in msg:
                        audlist.append(msg['net_audio'])
                    if 'apilink' in msg:
                        get_link = msg['apilink']
                    if 'url' in msg:
                        urllist.update({msg['url']: get_link})
                if status is None:
                    msglist = msglist.plusWith(MessageChain.create([Plain('发生错误：机器人内部代码错误，请联系开发者解决。')]))
            if msglist != MessageChain.create([]):
                await sendMessage(kwargs, msglist)
                if imglist != []:
                    imgchain = MessageChain.create([])
                    for img in imglist:
                        imgchain = imgchain.plusWith(MessageChain.create([Image.fromNetworkAddress(img)]))
                    await sendMessage(kwargs, imgchain, Quote=False)
                if audlist != []:
                    for aud in audlist:
                        audchain = MessageChain.create(
                            [Voice().fromLocalFile(await slk_converter(await download_to_cache(aud)))])
                        await sendMessage(kwargs, audchain, Quote=False)
            if urllist != {}:
                print(urllist)
                infoboxchain = MessageChain.create([])
                for url in urllist:
                    get_infobox = await get_infobox_pic(urllist[url], url, headers)
                    if get_infobox:
                        infoboxchain = infoboxchain.plusWith(
                            MessageChain.create([Image.fromLocalFile(get_infobox)]))
                if infoboxchain != MessageChain.create([]):
                    await sendMessage(kwargs, infoboxchain, Quote=False)
            if global_status == 'warn':
                trigger = kwargs[Target].id
                BotDB.warn_someone(trigger)
            if waitmsglist != MessageChain.create([]):
                send = await sendMessage(kwargs, waitmsglist)
                wait = await wait_confirm(kwargs)
                if wait:
                    nwaitlist = []
                    for waits in waitlist:
                        waits1 = f'[[{waits}]]'
                        nwaitlist.append(waits1)
                    await regex_proc(kwargs, '\n'.join(nwaitlist))
                else:
                    await revokeMessage(send)

    await regex_proc(kwargs, display)


command = {'wiki': wiki_loader, 'wiki_start_site': set_start_wiki, 'interwiki': interwiki}
regex = {'wiki_regex': regex_wiki}
options = ['wiki_fandom_addon']
help = {'wiki': {'help': '~wiki [interwiki:]<page_name> - 查询Wiki内容。\n' +
                         '~wiki set <api_endpoint_link> - 设置起始查询Wiki。\n' +
                         '~wiki iw <add/del> <interwiki> <wikiurl> - 设置自定义Interwiki跨站查询。\n' +
                         '~wiki headers <set/reset/show> - 设置请求标头。'},
        'wiki_start_site': {'help': '~wiki_start_site <api_endpoint_link> - 设置起始查询Wiki。'},
        'interwiki': {
            'help': '~interwiki <add/del> <interwiki> <wikiurl> - 设置自定义Interwiki跨站查询。'},
        'wiki_regex': {'help': '[[<page_name>]]|{{<page_name>}} - 当聊天中出现此种Wikitext时进行自动查询。'},
        'wiki_fandom_addon': {
            'help': '为Fandom定制的Wiki查询功能，包含有[[w:c:<wikiname>:[langcode:]<page_name>]]的消息会自动定向查询至Fandom的Wiki。'}}
