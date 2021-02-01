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
    display = kwargs[MessageChain].asDisplay()
    command_prefix = ['~', '～']
    if Group in kwargs:
        trigger = kwargs[Member].id
    if Friend in kwargs:
        trigger = kwargs[Friend].id
    if database.check_black_list(trigger):
        if not database.check_white_list(trigger):
            return
    if display[0] in command_prefix:
        command = re.sub(r'^' + display[0], '', display)
        command_first_word = command.split(' ')[0]
        if command_first_word in command_list:
            if Group in kwargs:
                check_command_enable = database.check_enable_modules(kwargs[Group].id, command_first_word)
                if check_command_enable:
                    check_command_enable_self = database.check_enable_modules_self(kwargs[Member].id,
                                                                                   command_first_word)
                    if check_command_enable_self:
                        kwargs['trigger_msg'] = command
                        await command_list[command_first_word](kwargs)
                else:
                    await sendMessage(kwargs, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
            else:
                check_command_enable_self = database.check_enable_modules_self(kwargs[Friend].id, command_first_word)
                if check_command_enable_self:
                    kwargs['trigger_msg'] = command
                    await command_list[command_first_word](kwargs)
        elif command_first_word in essential_list:
            kwargs['trigger_msg'] = command
            kwargs['function_list'] = function_list
            kwargs['help_list'] = help_list
            await essential_list[command_first_word](kwargs)
        elif command_first_word in admin_list:
            if database.check_superuser(kwargs):
                kwargs['trigger_msg'] = command
                kwargs['function_list'] = function_list
                await admin_list[command_first_word](kwargs)
            else:
                await sendMessage(kwargs, '权限不足')
    # regex
    if Group in kwargs:
        for regex in regex_list:
            check_command_enable = database.check_enable_modules(kwargs[Group].id,
                                                                 regex)
            if check_command_enable:
                check_command_enable_self = database.check_enable_modules_self(kwargs[Member].id, regex)
                if check_command_enable_self:
                    await regex_list[regex](kwargs)
    if Friend in kwargs:
        for regex in regex_list:
            check_command_enable_self = database.check_enable_modules_self(kwargs[Friend].id, regex)
            if check_command_enable_self:
                await regex_list[regex](kwargs)
