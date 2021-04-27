import re

import eventlet
from graia.application import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain

from core.elements import Target
from core.loader import Modules
from core.template import sendMessage, Nudge
from core.utils import getsetu
from database import BotDB as database


async def parser(kwargs: dict):
    """
    接收消息必经的预处理器
    :param kwargs: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    try:
        eventlet.monkey_patch()
        with eventlet.Timeout(90):
            if 'TEST' in kwargs:
                display = kwargs['command']
            else:
                display = kwargs[MessageChain].asDisplay()  # 将消息转换为一般显示形式
            if len(display) == 0:  # 转换后若为空消息则停止执行
                return
            command_prefix = ['~', '～']  # 消息前缀
            if Group in kwargs:  # 若为群组
                trigger = kwargs[Member].id
            if Friend in kwargs:  # 若为好友
                trigger = kwargs[Friend].id
            if 'TEST' in kwargs:
                trigger = 0
            if trigger == 1143754816:  # 特殊规则
                display = re.sub('^.*:\n', '', display)
            if database.check_black_list(trigger):  # 检查是否在黑名单
                if not database.check_white_list(trigger):  # 检查是否在白名单
                    return  # 在黑名单且不在白名单，给我爪巴
            if display.find('色图来') != -1:  # 双倍快乐给我爬
                await getsetu(kwargs)
                return
            if display[0] in command_prefix:  # 检查消息前缀
                command = re.sub(r'^' + display[0], '', display)
                command_first_word = command.split(' ')[0]  # 切割消息
                if command_first_word in Modules['command']:  # 检查触发命令是否在模块列表中
                    if Group in kwargs:
                        await Nudge(kwargs)
                        check_command_enable = database.check_enable_modules(kwargs[Group].id,
                                                                             command_first_word)  # 检查群组是否开启模块
                        if check_command_enable:  # 若开启
                            kwargs['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                            kwargs['help_list'] = Modules['help']  # 帮助列表
                            await Modules['command'][command_first_word](kwargs)  # 将dict传入下游模块
                        else:
                            await sendMessage(kwargs, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
                    elif 'TEST' in kwargs:
                        kwargs['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                        kwargs['help_list'] = Modules['help']  # 帮助列表
                        await Modules['command'][command_first_word](kwargs)  # 将dict传入下游模块
                    else:
                        kwargs['trigger_msg'] = command
                        kwargs['help_list'] = Modules['help']
                        await Modules['command'][command_first_word](kwargs)
                elif command_first_word in Modules['essential']:  # 若触发的对象命令为基础命令
                    await Nudge(kwargs)
                    kwargs['trigger_msg'] = command
                    kwargs['function_list'] = Modules['modules_function']  # 所有可用模块列表
                    kwargs['friend_function_list'] = Modules['friend_modules_function']
                    kwargs['help_list'] = Modules['help']
                    await Modules['essential'][command_first_word](kwargs)
                elif command_first_word in Modules['admin']:  # 若触发的对象为超管命令
                    if database.check_superuser(kwargs):  # 检查是否为超管
                        kwargs['trigger_msg'] = command
                        kwargs['function_list'] = Modules['modules_function']
                        await Modules['admin'][command_first_word](kwargs)
                    else:
                        await sendMessage(kwargs, '权限不足')
            # 正则模块部分
            if Group in kwargs:
                for regex in Modules['regex']:  # 遍历正则模块列表
                    check_command_enable = database.check_enable_modules(kwargs[Group].id,
                                                                         regex)  # 检查群组是否打开模块
                    if check_command_enable:
                        await Modules['regex'][regex](kwargs)  # 将整条dict传入下游正则模块
            if Friend in kwargs:
                for regex in Modules['regex']:
                    await Modules['regex'][regex](kwargs)
    except eventlet.timeout.Timeout:
        await sendMessage(kwargs, '发生错误：执行命令超时。')
