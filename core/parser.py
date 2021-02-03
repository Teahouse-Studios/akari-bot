import re

from graia.application import Friend
from graia.application.group import Group, Member
from graia.application.message.chain import MessageChain

import database
from core.loader import command_loader
from core.template import sendMessage

admin_list, essential_list, command_list, help_list, regex_list, self_options_list, options_list = command_loader()
print(essential_list)
function_list = []
for command in command_list:
    function_list.append(command)
for reg in regex_list:
    function_list.append(reg)
for options in self_options_list:
    function_list.append(options)
for options in options_list:
    function_list.append(options)
print(function_list)


async def parser(kwargs: dict):
    """
    接收消息必经的预处理器
    :param kwargs: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    display = kwargs[MessageChain].asDisplay()  # 将消息转换为一般显示形式
    command_prefix = ['~', '～']  # 消息前缀
    if Group in kwargs:  # 若为群组
        trigger = kwargs[Member].id
    if Friend in kwargs:  # 若为好友
        trigger = kwargs[Friend].id
    if database.check_black_list(trigger):  # 检查是否在黑名单
        if not database.check_white_list(trigger):  # 检查是否在白名单
            return  # 在黑名单且不在白名单，给我爪巴
    if display[0] in command_prefix:  # 检查消息前缀
        command = re.sub(r'^' + display[0], '', display)
        command_first_word = command.split(' ')[0]  # 切割消息
        if command_first_word in command_list:  # 检查触发命令是否在模块列表中
            if Group in kwargs:
                check_command_enable = database.check_enable_modules(kwargs[Group].id, command_first_word)  # 检查群组是否开启模块
                if check_command_enable:  # 若开启
                    check_command_enable_self = database.check_enable_modules_self(kwargs[Member].id,
                                                                                   command_first_word)
                    if check_command_enable_self:
                        kwargs['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                        kwargs['help_list'] = help_list  # 帮助列表
                        await command_list[command_first_word](kwargs)  # 将dict传入下游模块
                else:
                    await sendMessage(kwargs, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
            else:
                check_command_enable_self = database.check_enable_modules_self(kwargs[Friend].id, command_first_word)  # 检查个人是否开启模块
                if check_command_enable_self:
                    kwargs['trigger_msg'] = command
                    kwargs['help_list'] = help_list
                    await command_list[command_first_word](kwargs)
        elif command_first_word in essential_list:  # 若触发的对象命令为基础命令
            kwargs['trigger_msg'] = command
            kwargs['function_list'] = function_list  # 所有可用模块列表
            kwargs['help_list'] = help_list
            await essential_list[command_first_word](kwargs)
        elif command_first_word in admin_list:  # 若触发的对象为超管命令
            if database.check_superuser(kwargs):  # 检查是否为超管
                kwargs['trigger_msg'] = command
                kwargs['function_list'] = function_list
                await admin_list[command_first_word](kwargs)
            else:
                await sendMessage(kwargs, '权限不足')
    # 正则模块部分
    if Group in kwargs:
        for regex in regex_list:  # 遍历正则模块列表
            check_command_enable = database.check_enable_modules(kwargs[Group].id,
                                                                 regex)  # 检查群组是否打开模块
            if check_command_enable:
                check_command_enable_self = database.check_enable_modules_self(kwargs[Member].id, regex)  # 检查个人是否打开模块
                if check_command_enable_self:
                    await regex_list[regex](kwargs)  # 将整条dict传入下游正则模块
    if Friend in kwargs:
        for regex in regex_list:
            check_command_enable_self = database.check_enable_modules_self(kwargs[Friend].id, regex)
            if check_command_enable_self:
                await regex_list[regex](kwargs)
