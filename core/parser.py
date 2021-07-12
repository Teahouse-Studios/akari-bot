import re
import traceback

from graia.application import Friend
from graia.application.group import Group

from core.loader import Modules, ModulesAliases
from core.logger import Logger
from core.template import sendMessage, Nudge, kwargs_GetTrigger, kwargs_AsDisplay, RemoveDuplicateSpace
from core.utils import remove_ineffective_text
from database import BotDBUtil

command_prefix = ['~', '～']  # 消息前缀


async def parser(infochain: dict):
    """
    接收消息必经的预处理器
    :param infochain: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    display = RemoveDuplicateSpace(kwargs_AsDisplay(infochain))  # 将消息转换为一般显示形式
    targetInfo = BotDBUtil.TargetInfo(infochain)
    if targetInfo.isBanned or len(display) == 0:
        return
    if display[0] in command_prefix:  # 检查消息前缀
        Logger.info(infochain)
        command = re.sub(r'^' + display[0], '', display)
        command_list = remove_ineffective_text(command_prefix, command.split('&&'))  # 并行命令处理
        if len(command_list) > 5 and not targetInfo.isSuperUser:
            await sendMessage(infochain, '你不是本机器人的超级管理员，最多只能并排执行5个命令。')
            return
        for command in command_list:
            command_spilt = command.split(' ')  # 切割消息
            try:
                infochain['trigger_msg'] = command  # 触发该命令的消息，去除消息前缀
                command_first_word = command_spilt[0]
                if command_first_word in ModulesAliases:
                    command_spilt[0] = ModulesAliases[command_first_word]
                    command = ' '.join(command_spilt)
                    command_spilt = command.split(' ')
                    command_first_word = command_spilt[0]
                    infochain['trigger_msg'] = command
                if command_first_word in Modules:  # 检查触发命令是否在模块列表中
                    await Nudge(infochain)
                    module = Modules[command_first_word]
                    if module.is_superuser_function:
                        if not targetInfo.isSuperUser:
                            await sendMessage(infochain, '你没有使用该命令的权限。')
                    if module.is_admin_function:

                    if not module.is_base_function:
                        check_command_enable = BotDBUtil.Module(infochain).check_target_enabled_module(command_first_word)  # 检查群组是否开启模块
                        if not check_command_enable:  # 若未开启
                            await sendMessage(infochain, f'此模块未启用，请管理员在群内发送~enable {command_first_word}启用本模块。')
                            return
                await Modules[command_first_word].function(infochain)  # 将dict传入下游模块
            except Exception as e:
                traceback.print_exc()
                await sendMessage(infochain, '执行命令时发生错误，请报告管理员：\n' + str(e))
    #for regex in Modules['regex']:  # 遍历正则模块列表
    #    check_command_enable = database.check_enable_modules(infochain[Group].id,
    #                                                         regex)  # 检查群组是否打开模块
    #    if check_command_enable:
    #        await Modules['regex'][regex](infochain)  # 将整条dict传入下游正则模块
