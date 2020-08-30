import asyncio
import random
import re
from os.path import abspath

import graia.application.interrupt as inter
from graia.application import FriendMessage, GroupMessage, TempMessage
from graia.application.interrupt.interrupts import GroupMessageInterrupt, FriendMessageInterrupt, TempMessageInterrupt
from graia.application.message.chain import MessageChain
from graia.application.message.elements.internal import Plain, Image, UploadMethods, Source

from CommandGen import command
from modules.findimage import findimage


async def gen(bcc, app, message, target1, target2='0', msgtype='None'):
    im = inter.InterruptControl(bcc)
    if msgtype == 'group':
        run = await command(message.asDisplay(),target1.id)
    else:
        run = await command(message.asDisplay())
#    print(run)
    if run != None:
        print(run)
        msgchain = await makemsgchain(run, msgtype)
        if msgtype == 'friend':
            friend = target1
            send = await app.sendFriendMessage(friend, msgchain.asSendable())
        elif msgtype == 'group':
            group = target1
            member = target2
            send = await app.sendGroupMessage(group, msgchain.asSendable(), quote=message[Source][0])
        elif msgtype == 'temp':
            group = target1
            member = target2
            send = await app.sendTempMessage(group=group, target=member, message=msgchain.asSendable())
        else:
            print('错误：消息来源有误')
        if run.find('[一分钟后撤回本消息]') != -1:
            await asyncio.sleep(60)
            await app.revokeMessage(send)
        elif run.find('[30秒后撤回本消息]') != -1:
            await asyncio.sleep(30)
            await app.revokeMessage(send)
        if msgtype == 'friend':
            friend = target1
        elif msgtype == 'group':
            group = target1
            member = target2
        elif msgtype == 'temp':
            group = target1
            member = target2
        if run.find('[wait]') != -1:
            ranint = random.randint(1, 3)
            if ranint == 2:
                randmessage = await makemsgchain('提示：你可以发送“是”字来将所有无效结果再次查询。（考虑到实现复杂性，恕不提供选择性查询）', msgtype)
                if msgtype == 'friend':
                    friend = target1
                    await app.sendFriendMessage(friend, randmessage.asSendable())
                elif msgtype == 'group':
                    group = target1
                    member = target2
                    await app.sendGroupMessage(group, randmessage.asSendable())
                elif msgtype == 'temp':
                    group = target1
                    member = target2
                    await app.sendTempMessage(group=group, target=member, message=randmessage.asSendable())
                else:
                    print('错误：消息来源有误')
            if msgtype == 'friend':
                event: FriendMessage = await im.wait(FriendMessageInterrupt(friend))
            elif msgtype == 'group':
                event: GroupMessage = await im.wait(GroupMessageInterrupt(group, member))
            elif msgtype == 'temp':
                event: TempMessage = await im.wait(TempMessageInterrupt(group, member))
            print(event)
            if event.messageChain.asDisplay() == '是':
                msg2 = await command(run)
                msgchain = await makemsgchain(msg2, msgtype)
                if msgtype == 'friend':
                    friend = target1
                    await app.sendFriendMessage(friend, msgchain.asSendable())
                elif msgtype == 'group':
                    group = target1
                    await app.sendGroupMessage(group, msgchain.asSendable())
                elif msgtype == 'temp':
                    group = target1
                    member = target2
                    await app.sendTempMessage(group=group, target=member, message=msgchain.asSendable())
                else:
                    print('错误：消息来源有误')

            else:
                pass


async def makemsgchain(msg, msgtype):
    msg = re.sub('\[wait\]', '', msg)
    if msgtype == 'friend':
        mth = UploadMethods.Friend
    elif msgtype == 'group':
        mth = UploadMethods.Group
    elif msgtype == 'temp':
        mth = UploadMethods.Temp
    else:
        mth = None
    if msg.find('[[usn:') != -1:
        user = re.sub(r'.*\[\[usn:|\]\]', '', msg)
        msg = re.sub(r'\[\[.*\]\]', '', msg)
        msgchain = MessageChain.create(
            [Plain(msg)])
        msgchain = msgchain.plusWith(
            [Image.fromLocalFile(filepath=abspath(f"./assests/usercard/{user}.png"), method=mth)])
    else:
        msgchain = MessageChain.create(
            [Plain(msg)])
    r = re.findall(r'(https?://.*?/File:.*?\.(?:png|gif|jpg|jpeg|webp|bmp|ico))', msg, re.I)
    for d in r:
        d1 = await findimage(d)
        print(d1)
        msgchain = msgchain.plusWith([Image.fromNetworkAddress(url=d1, method=mth)])
    return msgchain
