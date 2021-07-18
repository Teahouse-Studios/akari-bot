import re
import traceback

from core.elements import MsgInfo
from core.loader import Modules, ModulesAliases
from core.logger import Logger
from core.template import sendMessage, Nudge, kwargs_AsDisplay, RemoveDuplicateSpace
from core.utils import remove_ineffective_text
from database import BotDBUtil

command_prefix = ['~', '～']  # 消息前缀


async def parser(message: dict):
    """
    接收消息必经的预处理器
    :param message: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    display = RemoveDuplicateSpace(kwargs_AsDisplay(message))  # 将消息转换为一般显示形式
    senderInfo = BotDBUtil.SenderInfo(message[MsgInfo].senderId)
    if senderInfo.query.isInBlackList and not senderInfo.query.isInWhiteList or len(display) == 0:
        return
    if display[0] in command_prefix:  # 检查消息前缀
        Logger.info(message)
        command = re.sub(r'^' + display[0], '', display)
        command_list = remove_ineffective_text(command_prefix, command.split('&&'))  # 并行命令处理
        if len(command_list) > 5 and not senderInfo.query.isSuperUser:
            await sendMessage(message, '你不是本机器人的超级管理员，最多只能并排执行5个命令。')
            return
        for command in command_list:
            command_spilt = command.split(' ')  # 切割消息
            try:
                message['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                command_first_word = command_spilt[0]
                if command_first_word in ModulesAliases:
                    command_spilt[0] = ModulesAliases[command_first_word]
                    command = ' '.join(command_spilt)
                    command_spilt = command.split(' ')
                    command_first_word = command_spilt[0]
                    message['trigger_msg'] = command
                if command_first_word == 'ping':
                    await sendMessage(message, 'pong')
                if command_first_word in Modules:  # 检查触发命令是否在模块列表中
                    await Nudge(message)
                    module = Modules[command_first_word]
                    if module.is_superuser_function:
                        if not senderInfo.query.isSuperUser:
                            await sendMessage(message, '你没有使用该命令的权限。')
                    if module.is_admin_function:
                        ...
                    if not module.is_base_function:
                        check_command_enable = BotDBUtil.Module(message).check_target_enabled_module(command_first_word)  # 检查群组是否开启模块
                        if not check_command_enable:  # 若未开启
                            await sendMessage(message, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
                            return
                    await Modules[command_first_word].function(message)  # 将dict传入下游模块
            except Exception as e:
                traceback.print_exc()
                await sendMessage(message, '执行命令时发生错误，请报告管理员：\n' + str(e))
    #for regex in Modules['regex']:  # 遍历正则模块列表
    #    check_command_enable = database.check_enable_modules(senderId[Group].id,
    #                                                         regex)  # 检查群组是否打开模块
    #    if check_command_enable:
    #        await Modules['regex'][regex](senderId)  # 将整条dict传入下游正则模块
