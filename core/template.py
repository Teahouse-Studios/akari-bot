import eventlet
from graia.application import MessageChain, GroupMessage, FriendMessage
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Plain, Image, Source
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

from core.broadcast import app, bcc
from database import check_superuser


async def sendMessage(kwargs: dict, msgchain):
    if isinstance(msgchain, str):
        msgchain = MessageChain.create([Plain(msgchain)])
    if Group in kwargs:
        try:
            eventlet.monkey_patch()
            with eventlet.Timeout(15):
                send = await app.sendGroupMessage(kwargs[Group], msgchain, quote=kwargs[MessageChain][Source][0].id)
                return send
        except eventlet.timeout.Timeout:
            split_msg = msgchain.get(Plain)
            sent_msgs = []
            for msgs in split_msg:
                send = await app.sendGroupMessage(kwargs[Group], MessageChain.create([msgs]), quote=kwargs[MessageChain][Source][0].id)
                sent_msgs.append(send)
            split_img = msgchain.get(Image)
            for imgs in split_img:
                send = await app.sendGroupMessage(kwargs[Group], MessageChain.create([imgs]), quote=kwargs[MessageChain][Source][0].id)
                sent_msgs.append(send)
            return sent_msgs
    if Friend in kwargs:
        try:
            eventlet.monkey_patch()
            with eventlet.Timeout(15):
                send = await app.sendFriendMessage(kwargs[Friend], msgchain)
                return send
        except eventlet.timeout.Timeout:
            split_msg = msgchain.get(Plain)
            sent_msgs = []
            for msgs in split_msg:
                send = await app.sendFriendMessage(kwargs[Friend], MessageChain.create([msgs]))
                sent_msgs.append(send)
            split_img = msgchain.get(Image)
            for imgs in split_img:
                send = await app.sendFriendMessage(kwargs[Friend], MessageChain.create([imgs]))
                sent_msgs.append(send)
            return sent_msgs


async def wait_confirm(kwargs: dict):
    inc = InterruptControl(bcc)
    confirm_command = ["是", "对", 'yes', 'y']
    if Group in kwargs:
        @Waiter.create_using_function([GroupMessage])
        def waiter(waiter_group: Group,
                   waiter_member: Member, waiter_message: MessageChain):
            if all([
                waiter_group.id == kwargs[Group].id,
                waiter_member.id == kwargs[Member].id,
            ]):
                print(111)
                if waiter_message.asDisplay() in confirm_command:
                    return True
                else:
                    return False
    if Friend in kwargs:
        @Waiter.create_using_function([FriendMessage])
        def waiter(waiter_friend: Friend, waiter_message: MessageChain):
            if all([
                waiter_friend.id == kwargs[Friend].id,
            ]):
                if waiter_message.asDisplay() in confirm_command:
                    return True
                else:
                    return False

    return await inc.wait(waiter)


async def revokeMessage(msgchain):
    if isinstance(msgchain, list):
        for msg in msgchain:
            await app.revokeMessage(msg)
    else:
        await app.revokeMessage(msgchain)


def check_permission(kwargs):
    if Group in kwargs:
        if str(kwargs[Member].permission) in ['MemberPerm.Administrator', 'MemberPerm.Owner'] or check_superuser(
                kwargs[Member].id):
            return True
    if Friend in kwargs:
        if check_superuser(kwargs[Friend].id):
            return True
    return False