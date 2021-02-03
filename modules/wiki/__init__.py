import re

from graia.application import MessageChain
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Image, UploadMethods
from graia.application.message.elements.internal import Plain

import modules.wiki.database as database
import modules.wiki.wikilib
from core.template import sendMessage, check_permission, wait_confirm, revokeMessage
from database import warn_someone, check_enable_modules_self, check_enable_modules
from modules.wiki.helper import check_wiki_available
from .getinfobox import get_infobox_pic

langcode = ['ab', 'aa', 'af', 'sq', 'am', 'ar', 'hy', 'as', 'ay', 'az', 'ba', 'eu', 'bn', 'dz', 'bh', 'bi', 'br', 'bg',
            'my', 'be', 'km', 'ca', 'zh', 'co', 'hr', 'cs', 'da', 'nl', 'en', 'eo', 'et', 'fo', 'fa', 'fj', 'fi', 'fr',
            'fy', 'gl', 'gd', 'gv', 'ka', 'de', 'el', 'kl', 'gn', 'gu', 'ha', 'he', 'iw', 'hi', 'hu', 'is', 'id', 'in',
            'ia', 'ie', 'iu', 'ik', 'ga', 'it', 'ja', 'jv', 'kn', 'ks', 'kk', 'rw', 'ky', 'rn', 'ko', 'ku', 'lo', 'la',
            'lv', 'li', 'ln', 'lt', 'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr', 'mo', 'mn', 'na', 'ne', 'no', 'oc', 'or',
            'om', 'ps', 'pl', 'pt', 'pa', 'qu', 'rm', 'ro', 'ru', 'sm', 'sg', 'sa', 'sr', 'sh', 'st', 'tn', 'sn', 'sd',
            'si', 'ss', 'sk', 'sl', 'so', 'es', 'su', 'sw', 'sv', 'tl', 'tg', 'ta', 'tt', 'te', 'th', 'to', 'ts', 'tr',
            'tk', 'tw', 'ug', 'uk', 'ur', 'uz', 'vi', 'vo', 'cy', 'wo', 'xh', 'yi', 'yo', 'zu']


async def wiki_loader(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub(r'^wiki ', '', command)
    if Group in kwargs:
        start_table = 'start_wiki_link_group'
    if Friend in kwargs:
        start_table = 'start_wiki_link_self'
    get_link = database.get_start_wiki(start_table, kwargs[Group].id)
    if not get_link:
        if Group in kwargs:
            prompt = '没有指定起始Wiki，请管理员在群内发送~wiki_start_site <域名>来设定起始Wiki。\n例子：~wiki_start_site https://minecraft-zh.gamepedia.com/'
        if Friend in kwargs:
            prompt = '没有指定起始Wiki，请发送~wiki_start_site <域名>来设定起始Wiki。\n例子：~wiki_start_site https://minecraft-zh.gamepedia.com/'
        await sendMessage(kwargs, MessageChain.create([Plain(prompt)]))
    else:
        iw = None
        co = False
        if Group in kwargs:
            check_gamepedia_addon_enable = check_enable_modules(kwargs[Group].id,
                                                                'wiki_gamepedia_addon')
            if check_gamepedia_addon_enable:
                matchsite = re.match(r'~(.*?) (.*)', command)
                if matchsite:
                    get_link = 'https://' + matchsite.group(1) + '.gamepedia.com/api.php'
                    iw = 'gp:' + matchsite.group(1)
                    co = True
                    command = matchsite.group(2)
                matchgp = re.match(r'^gp:(.*?):(.*)', command)
                if matchgp:
                    get_link = 'https://' + matchgp.group(1) + '.gamepedia.com/api.php'
                    iw = 'gp:' + matchgp.group(1)
                    co = True
                    command = matchsite.group(2)
        print(co)
        matchinterwiki = re.match(r'(.*?):(.*)', command)
        if matchinterwiki and not co:
            if Group in kwargs:
                get_custom_iw = database.get_custom_interwiki('custom_interwiki_group', kwargs[Group].id,
                                                              matchinterwiki.group(1))
            if Friend in kwargs:
                get_custom_iw = database.get_custom_interwiki('custom_interwiki_self', kwargs[Friend].id,
                                                              matchinterwiki.group(1))
            if get_custom_iw:
                iw = matchinterwiki.group(1)
                get_link = get_custom_iw
                command = re.sub(matchinterwiki.group(1) + ':', '', command)
        msg = await wikilib.wikilib().main(get_link, command, interwiki=iw)
        if msg['status'] == 'done':
            msgchain = MessageChain.create([Plain((msg['url'] + '\n' if 'url' in msg else '') + msg['text'])])
            if 'net_image' in msg:
                try:
                    if Group in kwargs:
                        mth = UploadMethods.Group
                    elif Friend in kwargs:
                        mth = UploadMethods.Friend
                    imgchain = MessageChain.create([Image.fromNetworkAddress(msg['net_image'], method=mth)])
                    msgchain = msgchain.plusWith(imgchain)
                except:
                    pass
            await sendMessage(kwargs, msgchain)
            if 'apilink' in msg:
                get_link = msg['apilink']
            if 'url' in msg:
                check_options = check_enable_modules_self(kwargs[Member].id if Group in kwargs else kwargs[Friend].id,
                                                          'wiki_infobox')
                print(check_options)
                if check_options:
                    pic = await get_infobox_pic(get_link, msg['url'])
                    if Group in kwargs:
                        mth = UploadMethods.Group
                    elif Friend in kwargs:
                        mth = UploadMethods.Friend
                    imgchain = MessageChain.create([Image.fromLocalFile(pic, method=mth)])
                    await sendMessage(kwargs, imgchain)

        elif msg['status'] == 'wait':
            await sendMessage(kwargs, MessageChain.create([Plain(msg['text'])]))
            wait = await wait_confirm(kwargs)
            if wait:
                msg = await wikilib.wikilib().main(get_link, msg['title'])
                await sendMessage(kwargs, MessageChain.create([Plain(msg['title'])]))
        elif msg['status'] == 'warn':
            if Group in kwargs:
                trigger = kwargs[Member].id
            if Friend in kwargs:
                trigger = kwargs[Friend].id
            warn_someone(trigger)
            await sendMessage(kwargs, MessageChain.create([Plain(msg['text'])]))


async def set_start_wiki(kwargs: dict):
    if Group in kwargs:
        if check_permission(kwargs):
            command = kwargs['trigger_msg']
            command = re.sub(r'^wiki_start_site ', '', command)
            check = await check_wiki_available(command)
            if check:
                result = database.add_start_wiki('start_wiki_link_group', kwargs[Group].id, check[0])
                await sendMessage(kwargs, MessageChain.create([Plain(result + check[1])]))
            else:
                result = '错误：此Wiki不是一个有效的MediaWiki/尝试建立连接超时。'
                await sendMessage(kwargs, MessageChain.create([Plain(result)]))
        else:
            result = '你没有使用该命令的权限。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
    if Friend in kwargs:
        command = kwargs['trigger_msg']
        command = re.sub(r'^wiki_start_site ', '', command)
        check = await check_wiki_available(command)
        if check:
            result = database.add_start_wiki('start_wiki_link_self', kwargs[Friend].id, check[0])
            await sendMessage(kwargs, MessageChain.create([Plain(result + check[1])]))
        else:
            result = '错误：此Wiki不是一个有效的MediaWiki/尝试建立连接超时。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))


async def interwiki(kwargs: dict):
    command = kwargs['trigger_msg']
    command = re.sub(r'^interwiki ', '', command)
    command = command.split(' ')
    if Group in kwargs:
        check = check_permission(kwargs)
        if check:
            if command[0] == 'add':
                iw = command[1].split('>')
                try:
                    check = await check_wiki_available(iw[1])
                except:
                    await sendMessage(kwargs, '错误：命令不合法：~interwiki add Interwiki>url')
                if check:
                    result = database.config_custom_interwiki('add', 'custom_interwiki_group', kwargs[Group].id, iw[0],
                                                              check[0])
                    await sendMessage(kwargs, MessageChain.create([Plain(result + check[1])]))
                else:
                    result = '错误：此Wiki不是一个有效的MediaWiki/尝试建立连接超时。'
                    await sendMessage(kwargs, MessageChain.create([Plain(result)]))
            elif command[0] == 'del':
                result = database.config_custom_interwiki('del', 'custom_interwiki_group', kwargs[Group].id, command[1])
                await sendMessage(kwargs, MessageChain.create([Plain(result)]))
            else:
                await sendMessage(kwargs, '命令不合法。')
        else:
            result = '你没有使用该命令的权限。'
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
    if Friend in kwargs:
        if command[0] == 'add':
            iw = command[1].split('>')
            check = await check_wiki_available(iw[1])
            if check:
                result = database.config_custom_interwiki('add', 'custom_interwiki_self', kwargs[Friend].id, iw[0],
                                                          check[0])
                await sendMessage(kwargs, MessageChain.create([Plain(result + check[1])]))
            else:
                result = '错误：此Wiki不是一个有效的MediaWiki/尝试建立连接超时。'
                await sendMessage(kwargs, MessageChain.create([Plain(result)]))
        elif command[0] == 'del':
            result = database.config_custom_interwiki('del', 'custom_interwiki_self', kwargs[Friend].id, command[1])
            await sendMessage(kwargs, MessageChain.create([Plain(result)]))
        else:
            await sendMessage(kwargs, '命令不合法。')


async def regex_wiki(kwargs: dict):
    display = kwargs[MessageChain].asDisplay()

    async def regex_proc(kwargs: dict, display):
        mains = re.findall(r'\[\[(.*?)\]\]', display, re.I)
        templates = re.findall(r'\{\{(.*?)\}\}', display, re.I)
        find_dict = {}
        global_status = 'done'
        for main in mains:
            if main == '' or main in find_dict:
                pass
            else:
                find_dict.update({main: 'main'})
        for template in templates:
            if template == '' or template in find_dict:
                pass
            else:
                find_dict.update({template: 'template'})
        if find_dict != {}:
            waitlist = []
            imglist = []
            urllist = {}
            msglist = MessageChain.create([])
            waitmsglist = MessageChain.create([])
            if Group in kwargs:
                table = 'start_wiki_link_group'
                target = kwargs[Group].id
                mth = UploadMethods.Group
            if Friend in kwargs:
                table = 'start_wiki_link_self'
                target = kwargs[Friend].id
                mth = UploadMethods.Friend
            for find in find_dict:
                if find_dict[find] == 'template':
                    template = True
                else:
                    template = False
                get_link = database.get_start_wiki(table, target)
                if not get_link:
                    if Group in kwargs:
                        prompt = '没有指定起始Wiki，请管理员在群内发送~wiki_start_site <域名>来设定起始Wiki。\n例子：~wiki_start_site https://minecraft-zh.gamepedia.com/'
                    if Friend in kwargs:
                        prompt = '没有指定起始Wiki，请发送~wiki_start_site <域名>来设定起始Wiki。\n例子：~wiki_start_site https://minecraft-zh.gamepedia.com/'
                    msg = {}
                    msg['text'] = prompt
                    status = 'done'
                else:
                    iw = None
                    matchinterwiki = re.match(r'(.*?):(.*)', find)
                    if matchinterwiki:
                        if Group in kwargs:
                            iw_table = 'custom_interwiki_group'
                        if Friend in kwargs:
                            iw_table = 'custom_interwiki_self'
                        get_custom_iw = modules.wiki.database.get_custom_interwiki(iw_table,
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
                                    check_fandom_addon_enable = check_enable_modules(kwargs[Group].id,
                                                                                     'wiki_fandom_addon')
                                    if check_fandom_addon_enable:
                                        matchinterwiki = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                                        if matchinterwiki:
                                            matchlangcode = re.match(r'(.*?):(.*)', matchinterwiki.group(2))
                                            if matchlangcode:
                                                if matchlangcode.group(1) in langcode:
                                                    get_link = f'https://{matchinterwiki.group(1)}.fandom.com/{matchlangcode.group(1)}/api.php'
                                                    find = matchlangcode.group(2)
                                                    iw = matchinterwiki.group(1) + ':' + matchlangcode.group(1)
                                                else:
                                                    get_link = f'https://{matchinterwiki.group(1)}.fandom.com/api.php'
                                                    find = matchinterwiki.group(2)
                                                    iw = matchinterwiki.group(1)
                                            else:
                                                get_link = f'https://{matchinterwiki.group(1)}.fandom.com/api.php'
                                                find = matchinterwiki.group(2)
                                                iw = matchinterwiki.group(1)
                    msg = await modules.wiki.wikilib.wikilib().main(get_link, find, interwiki=iw, template=template)
                    status = msg['status']
                if status == 'wait':
                    global_status = 'wait'
                    waitlist.append(msg['title'])
                    waitmsglist = waitmsglist.plusWith(MessageChain.create(
                        [Plain(('\n' if msglist != MessageChain.create([]) else '') + msg['text'])]))
                if status == 'warn':
                    global_status = 'warn'
                    msglist = msglist.plusWith(MessageChain.create(
                        [Plain(('\n' if msglist != MessageChain.create([]) else '') + msg['text'])]))
                if status == 'done':
                    msglist = msglist.plusWith(MessageChain.create([Plain(
                        ('\n' if msglist != MessageChain.create([]) else '') + (
                            msg['url'] + '\n' if 'url' in msg else '') + msg['text'])]))
                    if 'net_image' in msg:
                        imglist.append(msg['net_image'])
                    if 'apilink' in msg:
                        get_link = msg['apilink']
                    if 'url' in msg:
                        urllist.update({msg['url']: get_link})
            if msglist != MessageChain.create([]):
                await sendMessage(kwargs, msglist)
                if imglist != []:
                    imgchain = MessageChain.create([])
                    for img in imglist:
                        imgchain = imgchain.plusWith(MessageChain.create([Image.fromNetworkAddress(img, method=mth)]))
                    await sendMessage(kwargs, imgchain)
            if urllist != {}:
                print(urllist)
                check_options = check_enable_modules_self(
                    kwargs[Member].id if Group in kwargs else kwargs[Friend].id, 'wiki_infobox')
                if check_options:
                    infoboxchain = MessageChain.create([])
                    for url in urllist:
                        get_infobox = await get_infobox_pic(urllist[url], url)
                        if get_infobox:
                            infoboxchain = infoboxchain.plusWith(
                                MessageChain.create([Image.fromLocalFile(get_infobox, method=mth)]))
                    if infoboxchain != MessageChain.create([]):
                        await sendMessage(kwargs, infoboxchain, Quote=False)
            if global_status == 'warn':
                if Group in kwargs:
                    trigger = kwargs[Member].id
                if Friend in kwargs:
                    trigger = kwargs[Friend].id
                warn_someone(trigger)
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
self_options = ['wiki_infobox']
options = ['wiki_fandom_addon', 'wiki_gamepedia_addon']
help = {'wiki': {'module': '查询Wiki内容。', 'help': '~wiki [interwiki:]<pagename> - 查询Wiki内容。'},
        'wiki_start_site': {'module': '设置起始查询Wiki。', 'help': '~wiki_start_site <wikilink> - 设置起始查询Wiki。'},
        'interwiki': {'module': '设置自定义Interwiki。',
                      'help': '~interwiki <add|del> <wikilink>><wikiurl> - 设置自定义Interwiki。'},
        'wiki_regex': {'module': '启用正则Wikitext查询。', 'help': '[[<pagename>]]|{{<pagename>}} - 当聊天中出现此种Wikitext时进行自动查询。'},
        'wiki_infobox': {'module': '当被查询的页面包含Infobox时自动提取并渲染为图片发送。',
                         'help': 'Infobox渲染已开启：当被查询的页面包含Infobox时自动提取并渲染为图片发送。（群聊默认开启且不可全局关闭，个人可使用~disable self wiki_infobox关闭）',
                         'depend': 'wiki'},
        'wiki_fandom_addon': {'module': '启用为Fandom定制的Wiki查询功能。（仅群聊）',
                              'help': '提示：为Fandom定制的Wiki查询功能已开启，现在包含有[[w:c:<wikiname>:[langcode:]<pagename>]]的消息会自动定向查询至Fandom的Wiki。'},
        'wiki_gamepedia_addom': {'module': '启用为Gamepedia定制的Wiki查询功能。（仅群聊）',
                                 'help': '提示：为Gamepedia定制的查询功能已开启，现在输入~wiki ~<wikiname> <pagename>会自动定向查询至Gamepedia的Wiki。'}}
