import re
import traceback

from graia.application import Friend
from graia.application.group import Group

from core.loader import Modules, ModulesAliases
from core.logger import Logger
from core.template import sendMessage, Nudge, kwargs_GetTrigger, kwargs_AsDisplay, RemoveDuplicateSpace
from core.utils import remove_ineffective_text
from database import BotDB as database

command_prefix = ['~', '～']  # 消息前缀


async def parser(kwargs: dict):
    """
    接收消息必经的预处理器
    :param kwargs: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    display = RemoveDuplicateSpace(kwargs_AsDisplay(kwargs))  # 将消息转换为一般显示形式
    if len(display) == 0:  # 转换后若为空消息则停止执行
        return
    trigger = kwargs_GetTrigger(kwargs)  # 得到触发者来源
    if trigger == 1143754816:  # 特殊规则
        display = re.sub('^.*:\n', '', display)
    if database.check_black_list(trigger):  # 检查是否在黑名单
        if not database.check_white_list(trigger):  # 检查是否在白名单
            return  # 在黑名单且不在白名单，给我爪巴
    if display.find('色图来') != -1:  # 双倍快乐给我爬
        return
    if display[0] in command_prefix:  # 检查消息前缀
        Logger.info(kwargs)
        command = re.sub(r'^' + display[0], '', display)
        command_list = remove_ineffective_text(command_prefix, command.split('&&'))  # 并行命令处理
        if len(command_list) > 5:
            if not database.check_superuser(kwargs):
                await sendMessage(kwargs, '你不是本机器人的超级管理员，最多只能并排执行5个命令。')
                return
        for command in command_list:
            command_spilt = command.split(' ')  # 切割消息
            try:
                kwargs['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                kwargs['bot_modules'] = Modules
                command_first_word = command_spilt[0]
                if command_first_word in ModulesAliases:
                    command_spilt[0] = ModulesAliases[command_first_word]
                    command = ' '.join(command_spilt)
                    command_spilt = command.split(' ')
                    command_first_word = command_spilt[0]
                    kwargs['trigger_msg'] = command
                if command_first_word in Modules:  # 检查触发命令是否在模块列表中
                    await Nudge(kwargs)
                    plugin = Modules[command_first_word]
                    if plugin.is_superuser_function:
                        ...
                    if plugin.is_admin_function:
                        ...
                    check_command_enable = database.check_enable_modules(kwargs[Group].id,
                                                                         command_first_word)  # 检查群组是否开启模块
                    #if not check_command_enable:  # 若未开启
                    #    await sendMessage(kwargs, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
                    #    return
                await Modules[command_first_word].function(kwargs)  # 将dict传入下游模块
            except Exception as e:
                traceback.print_exc()
                await sendMessage(kwargs, '执行命令时发生错误，请报告管理员：\n' + str(e))
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
    return
