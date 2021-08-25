import re
import traceback

from core.elements import MessageSession, Option, command_prefix
from core.loader import Modules, ModulesAliases, ModulesRegex
from core.logger import Logger
from core.parser.command import CommandParser, InvalidCommandFormatError, InvalidHelpDocTypeError
from core.utils import remove_ineffective_text, RemoveDuplicateSpace
from database import BotDBUtil


async def parser(msg: MessageSession):
    """
    接收消息必经的预处理器
    :param msg: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :return: 无返回
    """
    display = RemoveDuplicateSpace(msg.asDisplay())  # 将消息转换为一般显示形式
    msg.trigger_msg = display
    msg.target.senderInfo = senderInfo = BotDBUtil.SenderInfo(msg.target.senderId)
    enabled_modules_list = BotDBUtil.Module(msg).check_target_enabled_module_list()
    if senderInfo.query.isInBlackList and not senderInfo.query.isInWhiteList or len(display) == 0:
        return
    if display[0] in command_prefix:  # 检查消息前缀
        Logger.info(display)
        command = re.sub(r'^' + display[0], '', display)
        command_list = remove_ineffective_text(command_prefix, command.split('&&'))  # 并行命令处理
        if len(command_list) > 5 and not senderInfo.query.isSuperUser:
            await msg.sendMessage('你不是本机器人的超级管理员，最多只能并排执行5个命令。')
            return
        for command in command_list:
            command_spilt = command.split(' ')  # 切割消息
            try:
                msg.trigger_msg = command  # 触发该命令的消息，去除消息前缀
                command_first_word = command_spilt[0]
                if command_first_word in ModulesAliases:
                    command_spilt[0] = ModulesAliases[command_first_word]
                    command = ' '.join(command_spilt)
                    command_spilt = command.split(' ')
                    command_first_word = command_spilt[0]
                    msg.trigger_msg = command
                if command_first_word in Modules:  # 检查触发命令是否在模块列表中
                    module = Modules[command_first_word]
                    if isinstance(module, Option):
                        return await msg.sendMessage(module.desc)
                    if module.is_regex_function or module.autorun:
                        if module.help_doc is not None:
                            return await msg.sendMessage(CommandParser(module.help_doc).return_formatted_help_doc())
                        elif module.desc is not None:
                            return await msg.sendMessage(module.desc)
                    if module.need_superuser:
                        if not senderInfo.query.isSuperUser:
                            return await msg.sendMessage('你没有使用该命令的权限。')
                    elif not module.is_base_function:
                        if command_first_word not in enabled_modules_list:  # 若未开启
                            return await msg.sendMessage(f'此模块未启用，请发送~enable {command_first_word}启用本模块。')
                    if module.need_admin:
                        if not await msg.checkPermission():
                            return await msg.sendMessage('此命令仅能被该群组的管理员所使用，请联系管理员执行此命令。')
                    help_doc = module.help_doc
                    if help_doc is not None:
                        try:
                            command_parser = CommandParser(help_doc)
                            try:
                                msg.parsed_msg = command_parser.parse(command)
                            except InvalidCommandFormatError:
                                return await msg.sendMessage('语法错误。\n' + command_parser.return_formatted_help_doc())
                        except InvalidHelpDocTypeError:
                            return await msg.sendMessage('此模块的帮助信息有误，请联系开发者处理。\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
                    async with msg.Typing(msg):
                        await Modules[command_first_word].function(msg)  # 将dict传入下游模块
            except Exception as e:
                traceback.print_exc()
                await msg.sendMessage('执行命令时发生错误，请报告机器人开发者：\n' + str(e) + '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
    for regex in ModulesRegex:  # 遍历正则模块列表
        if regex in enabled_modules_list:
            await ModulesRegex[regex].function(msg)  # 将整条dict传入下游正则模块
