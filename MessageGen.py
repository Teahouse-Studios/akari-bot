import re
import asyncio
from graia.application.message.chain import MessageChain
from graia.application.message.elements.internal import Plain, Image, UploadMethods
from os.path import abspath

from CommandGen import command
from modules.findimage import findimage


async def gen(app, message, target1, target2='0', msgtype='None'):
    run = await command(message.asDisplay())
    print(run)
    if run != None:
        if msgtype == 'friend':
            mth = UploadMethods.Friend
        elif msgtype == 'group':
            mth = UploadMethods.Group
        elif msgtype == 'temp':
            mth = UploadMethods.Temp
        else:
            mth = None
        if run.find('[[usn:') != -1:
            user = re.sub(r'.*\[\[usn:|\]\]', '', run)
            msg = re.sub(r'\[\[.*\]\]', '', run)
            msgchain = MessageChain.create( \
                [Plain(msg)])
            msgchain = msgchain.plusWith(
                [Image.fromLocalFile(filepath=abspath(f"./assests/usercard/{user}.png"), method=mth)])
        else:
            msgchain = MessageChain.create( \
                [Plain(run)])
        r = re.findall(r'(https?://.*?/File:.*?\.(?:png|gif|jpg|jpeg|webp|bmp|ico))', run, re.I)
        for d in r:
            d1 = await findimage(d)
            print(d1)
            msgchain = msgchain.plusWith([Image.fromNetworkAddress(url=d1, method=mth)])
        if msgtype == 'friend':
            friend = target1
            send = await app.sendFriendMessage(friend, msgchain.asSendable())
        elif msgtype == 'group':
            group = target1
            member = target2
            send = await app.sendGroupMessage(group, msgchain.asSendable(), quote=message.__root__[0].id)
        elif msgtype == 'temp':
            group = target1
            member = target2
            send = await app.sendTempMessage(group=group, target=member, message=msgchain.asSendable())
        if run.find('[一分钟后撤回本消息]') != -1:
            await asyncio.sleep(60)
            await app.revokeMessage(send)
        elif run.find('[30秒后撤回本消息]') != -1:
            await asyncio.sleep(30)
            await app.revokeMessage(send)


from modules.wiki import im, imt, imarc


async def findwikitext(app, message, target1, target2='0', msgtype='None'):
    w = re.findall(r'\[\[(.*?)\]\]', message.asDisplay())
    w2 = re.findall(r'\{\{(.*?)\}\}', message.asDisplay())
    print(str(w), str(w2))

    z = []
    c = '\n'
    try:
        for x in w:
            if msgtype == 'group':
                group = target1
                if group.id == 250500369 or group.id == 676942198:
                    if x == '':
                        pass
                    else:
                        z.append(await imarc(x))
                else:
                    if x == '':
                        pass
                    else:
                        z.append(await im(x))
            else:
                if x == '':
                    pass
                else:
                    z.append(await im(x))
    except:
        pass
    try:
        if str(w2) == '['']' or str(w2) == '[]':
            pass
        else:
            for x in w2:
                if msgtype == 'group':
                    group = target1
                    if group.id == 250500369 or group.id == 676942198:
                        pass
                    else:
                        if x == '':
                            pass
                        else:
                            z.append(await imt(x))
                else:
                    if x == '':
                        pass
                    else:
                        z.append(await imt(x))
    except:
        pass
    if str(z) == '['']['']' or str(z) == '[][]' or str(z) == '[]':
        pass
    else:
        if msgtype == 'friend':
            mth = UploadMethods.Friend
        elif msgtype == 'group':
            mth = UploadMethods.Group
        elif msgtype == 'temp':
            mth = UploadMethods.Temp
        else:
            mth = None
        v = c.join(z)
        r = re.findall(r'(https?://.*?/File:.*?\.(?:png|gif|jpg|jpeg|webp|bmp|ico))', v, re.I)
        print(v)
        print(str(r))
        msgchain = MessageChain.create([Plain(v)])
        for d in r:
            d1 = await findimage(d)
            print(d1)
            msgchain = msgchain.plusWith([Image.fromNetworkAddress(url=d1, method=mth)])
        if msgtype == 'friend':
            friend = target1
            await app.sendFriendMessage(friend, msgchain.asSendable())
        elif msgtype == 'group':
            group = target1
            member = target2
            await app.sendGroupMessage(group, msgchain.asSendable(), quote=message.__root__[0].id)
        elif msgtype == 'temp':
            group = target1
            member = target2
            await app.sendTempMessage(group=group, target=member, message=msgchain.asSendable())
