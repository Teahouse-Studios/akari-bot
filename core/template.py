import asyncio
import traceback
import uuid
from os.path import abspath
import os

import aiohttp
import filetype as ft
from graia.application import MessageChain, GroupMessage, FriendMessage
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Plain, Image, Source
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

from core.elements import Target
from core.loader import logger_info
from core.broadcast import app, bcc
from database import BotDB as database


async def sendMessage(kwargs: dict, msgchain, Quote=True):
    """
    用于发送一条消息，兼容Group和Friend消息。
    :param kwargs: 函数传入的dict
    :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
    :param Quote: 是否引用传入dict中的消息（仅对Group消息有效）
    :return: 被发送的消息链
    """
    if isinstance(msgchain, str):
        if msgchain == '':
            msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
        msgchain = MessageChain.create([Plain(msgchain)])
    QuoteTarget = None
    if 'TEST' not in kwargs:
        if Quote:
            QuoteTarget = kwargs[MessageChain][Source][0].id
    if Group in kwargs:
        send = await app.sendGroupMessage(kwargs[Group], msgchain, quote=QuoteTarget)
        return send
    if Friend in kwargs:
        send = await app.sendFriendMessage(kwargs[Friend], msgchain)
        return send
    if 'From' in kwargs:
        if kwargs['From'] == 'Group':
            send = await app.sendGroupMessage(kwargs['ID'], msgchain)
            return send
        if kwargs['From'] == 'Friend':
            send = await app.sendFriendMessage(kwargs['ID'], msgchain)
            return send
    if 'TEST' in kwargs:
        print(msgchain.asDisplay())


async def wait_confirm(kwargs: dict):
    """
    一次性模板，用于等待触发对象确认，兼容Group和Friend消息
    :param kwargs: 函数传入的dict
    :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
    """
    inc = InterruptControl(bcc)
    confirm_command = ["是", "对", 'yes', 'y', '确定']
    if Group in kwargs:
        @Waiter.create_using_function([GroupMessage])
        def waiter(waiter_group: Group,
                   waiter_member: Member, waiter_message: MessageChain):
            if all([
                waiter_group.id == kwargs[Group].id,
                waiter_member.id == kwargs[Member].id,
            ]):
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


async def wait_anything(kwargs: dict):
    inc = InterruptControl(bcc)
    if Group in kwargs:
        @Waiter.create_using_function([GroupMessage])
        def waiter(waiter_group: Group,
                   waiter_member: Member, waiter_message: MessageChain):
            if all([
                waiter_group.id == kwargs[Group].id,
                waiter_member.id == kwargs[Member].id,
            ]):
                return True
    if Friend in kwargs:
        @Waiter.create_using_function([FriendMessage])
        def waiter(waiter_friend: Friend, waiter_message: MessageChain):
            if all([
                waiter_friend.id == kwargs[Friend].id,
            ]):
                return True

    return await inc.wait(waiter)


async def revokeMessage(msgchain):
    """
    用于撤回消息。
    :param msgchain: 需要撤回的已发送/接收的消息链
    :return: 无返回
    """
    if isinstance(msgchain, list):
        for msg in msgchain:
            await app.revokeMessage(msg)
    else:
        await app.revokeMessage(msgchain)


def check_permission(kwargs):
    """
    检查对象是否拥有某项权限
    :param kwargs: 从函数传入的dict
    :return: 若对象为群主、管理员或机器人超管则为True
    """
    if Group in kwargs:
        if str(kwargs[Member].permission) in ['MemberPerm.Administrator',
                                              'MemberPerm.Owner'] or database.check_superuser(
                kwargs):
            return True
    if Friend in kwargs:
        if database.check_superuser(kwargs[Friend].id):
            return True
    return False


async def download_to_cache(link):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as resp:
                res = await resp.read()
                ftt = ft.match(res).extension
                path = abspath(f'./cache/{str(uuid.uuid4())}.{ftt}')
                with open(path, 'wb+') as file:
                    file.write(res)
                    return path
    except:
        traceback.print_exc()
        return False


async def slk_converter(filepath):
    filepath2 = filepath + '.silk'
    logger_info('Start encoding voice...')
    os.system('python slk_coder.py ' + filepath)
    logger_info('Voice encoded.')
    return filepath2


async def Nudge(kwargs):
    if Group in kwargs:
        await app.nudge(kwargs[Member])
    if Friend in kwargs:
        await app.nudge(kwargs[Friend])
