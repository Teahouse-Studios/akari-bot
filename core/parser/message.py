import copy
import difflib
import re
import traceback
from datetime import datetime
from typing import List, Dict

from aiocqhttp.exceptions import ActionFailed

from config import Config
from core.builtins.message import MessageSession
from core.elements import Command, command_prefix, ExecutionLockList, RegexCommand, ErrorMessage
from core.elements.module.component_meta import CommandMeta
from core.exceptions import AbuseWarning, FinishedException, InvalidCommandFormatError, InvalidHelpDocTypeError, \
    WaitCancelException, NoReportException
from core.loader import ModulesManager
from core.logger import Logger
from core.parser.args import Template, ArgumentPattern, templates_to_str
from core.parser.command import CommandParser
from core.tos import warn_target
from core.utils import removeIneffectiveText, removeDuplicateSpace, MessageTaskManager
from database import BotDBUtil

enable_tos = Config('enable_tos')
enable_analytics = Config('enable_analytics')

counter_same = {}  # 命令使用次数计数（重复使用单一命令）
counter_all = {}  # 命令使用次数计数（使用所有命令）

temp_ban_counter = {}  # 临时限制计数


async def remove_temp_ban(msg: MessageSession):
    is_temp_banned = temp_ban_counter.get(msg.target.senderId)
    if is_temp_banned is not None:
        del temp_ban_counter[msg.target.senderId]


async def msg_counter(msg: MessageSession, command: str):
    same = counter_same.get(msg.target.senderId)
    if same is None or datetime.now().timestamp() - same['ts'] > 300 or same['command'] != command:
        # 检查是否滥用（重复使用同一命令）
        counter_same[msg.target.senderId] = {'command': command, 'count': 1,
                                             'ts': datetime.now().timestamp()}
    else:
        same['count'] += 1
        if same['count'] > 10:
            raise AbuseWarning('一段时间内使用相同命令的次数过多')
    all_ = counter_all.get(msg.target.senderId)
    if all_ is None or datetime.now().timestamp() - all_['ts'] > 300:  # 检查是否滥用（重复使用同一命令）
        counter_all[msg.target.senderId] = {'count': 1,
                                            'ts': datetime.now().timestamp()}
    else:
        all_['count'] += 1
        if all_['count'] > 20:
            raise AbuseWarning('一段时间内使用命令的次数过多')


async def temp_ban_check(msg: MessageSession):
    is_temp_banned = temp_ban_counter.get(msg.target.senderId)
    if is_temp_banned is not None:
        ban_time = datetime.now().timestamp() - is_temp_banned['ts']
        if ban_time < 300:
            if is_temp_banned['count'] < 2:
                is_temp_banned['count'] += 1
                return await msg.finish('提示：\n'
                                        '由于你的行为触发了警告，我们已对你进行临时限制。\n'
                                        f'距离解封时间还有{str(int(300 - ban_time))}秒。')
            elif is_temp_banned['count'] <= 5:
                is_temp_banned['count'] += 1
                return await msg.finish('即使是触发了临时限制，继续使用命令还是可能会导致你被再次警告。\n'
                                        f'距离解封时间还有{str(int(300 - ban_time))}秒。')
            else:
                raise AbuseWarning('无视临时限制警告')


async def parser(msg: MessageSession, require_enable_modules: bool = True, prefix: list = None,
                 running_mention: bool = False):
    """
    接收消息必经的预处理器
    :param msg: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :param require_enable_modules: 是否需要检查模块是否已启用
    :param prefix: 使用的命令前缀。如果为None，则使用默认的命令前缀，存在''值的情况下则代表无需命令前缀
    :param running_mention: 消息内若包含机器人名称，则检查是否有命令正在运行
    :return: 无返回
    """
    identify_str = f'[{msg.target.senderId}{f" ({msg.target.targetId})" if msg.target.targetFrom != msg.target.senderFrom else ""}]'
    # Logger.info(f'{identify_str} -> [Bot]: {display}')
    try:
        MessageTaskManager.check(msg)
        modules = ModulesManager.return_modules_list_as_dict(msg.target.targetFrom)
        modulesAliases = ModulesManager.return_modules_alias_map()
        modulesRegex: Dict[str, RegexCommand] = ModulesManager.return_specified_type_modules(RegexCommand,
                                                                                             targetFrom=msg.target.targetFrom)

        display = removeDuplicateSpace(msg.asDisplay())  # 将消息转换为一般显示形式
        if len(display) == 0:
            return
        msg.trigger_msg = display
        msg.target.senderInfo = senderInfo = BotDBUtil.SenderInfo(msg.target.senderId)
        if senderInfo.query.isInBlockList and not senderInfo.query.isInAllowList:
            return ExecutionLockList.remove(msg)
        msg.prefixes = command_prefix.copy()  # 复制一份作为基础命令前缀
        get_custom_alias = msg.options.get('command_alias')
        if get_custom_alias is not None:
            get_display_alias = get_custom_alias.get(msg.trigger_msg)
            if get_display_alias is not None:
                msg.trigger_msg = display = get_display_alias
        get_custom_prefix = msg.options.get('command_prefix')  # 获取自定义命令前缀
        if get_custom_prefix is not None:
            msg.prefixes = get_custom_prefix + msg.prefixes  # 混合

        disable_prefix = False
        if prefix is not None:  # 如果上游指定了命令前缀，则使用指定的命令前缀
            if '' in prefix:
                disable_prefix = True
            msg.prefixes.clear()
            msg.prefixes.extend(prefix)
        display_prefix = ''
        in_prefix_list = False
        for cp in msg.prefixes:  # 判断是否在命令前缀列表中
            if display.startswith(cp):
                display_prefix = cp
                in_prefix_list = True
                break

        if in_prefix_list or disable_prefix:  # 检查消息前缀
            if len(display) <= 1 or display[:2] == '~~':  # 排除 ~~xxx~~ 的情况
                return

            Logger.info(
                f'{identify_str} -> [Bot]: {display}')

            if disable_prefix and not in_prefix_list:
                command = display
            else:
                command = display[len(display_prefix):]

            command_list = removeIneffectiveText(display_prefix, command.split('&&'))  # 并行命令处理

            if len(command_list) > 5 and not senderInfo.query.isSuperUser:
                return await msg.sendMessage('你不是本机器人的超级管理员，最多只能并排执行5个命令。')

            if not ExecutionLockList.check(msg):  # 加锁
                ExecutionLockList.add(msg)
            else:
                return await msg.sendMessage('您有命令正在执行，请稍后再试。')

            for command in command_list:
                no_alias = False
                for moduleName in modules:
                    if command.startswith(moduleName):  # 判断此命令是否匹配一个实际的模块
                        no_alias = True
                if not no_alias:  # 如果没有匹配到模块，则判断是否匹配命令别名
                    alias_list = []
                    for alias in modulesAliases:
                        if command.startswith(alias) and not command.startswith(modulesAliases[alias]):
                            alias_list.append(alias)
                    if alias_list:
                        max_ = max(alias_list, key=len)
                        command = command.replace(max_, modulesAliases[max_], 1)
                command_split: list = command.split(' ')  # 切割消息
                msg.trigger_msg = command  # 触发该命令的消息，去除消息前缀
                command_first_word = command_split[0].lower()

                if command_first_word not in modules:
                    """if msg.options.get('typo_check', True):  # 判断是否开启错字检查  todo: alias检查
                        nmsg, command_first_word, command_split = await typo_check(msg, display_prefix, modules,
                                                                                   command_first_word, command_split)
                        if nmsg is None:
                            return ExecutionLockList.remove(msg)
                        msg = nmsg"""

                sudo = False
                mute = False
                if command_first_word == 'mute':
                    mute = True
                if command_first_word == 'sudo':
                    if not msg.checkSuperUser():
                        return await msg.sendMessage('你不是本机器人的超级管理员，无法使用sudo命令。')
                    sudo = True
                    del command_split[0]
                    command_first_word = command_split[0].lower()
                    msg.trigger_msg = ' '.join(command_split)

                in_mute = msg.muted
                if in_mute and not mute:
                    return ExecutionLockList.remove(msg)

                if command_first_word in modules:  # 检查触发命令是否在模块列表中
                    time_start = datetime.now()
                    try:
                        if enable_tos:
                            await temp_ban_check(msg)

                        module = modules[command_first_word]
                        if not isinstance(module, Command):  # 如果不是Command类，则展示模块简介
                            if module.desc is not None:
                                desc = f'介绍：\n{module.desc}'
                                if command_first_word not in msg.enabled_modules:
                                    desc += f'\n{command_first_word}模块未启用，请发送{msg.prefixes[0]}enable {command_first_word}启用本模块。'
                                await msg.sendMessage(desc)
                            continue

                        if module.required_superuser:
                            if not msg.checkSuperUser():
                                await msg.sendMessage('你没有使用该命令的权限。')
                                continue
                        elif not module.base:
                            if command_first_word not in msg.enabled_modules and not sudo and require_enable_modules:  # 若未开启
                                await msg.sendMessage(
                                    f'{command_first_word}模块未启用，请发送{msg.prefixes[0]}enable {command_first_word}启用本模块。')
                                continue
                        elif module.required_admin:
                            if not await msg.checkPermission():
                                await msg.sendMessage(f'{command_first_word}命令仅能被该群组的管理员所使用，请联系管理员执行此命令。')
                                continue

                        if not module.match_list.set:
                            await msg.sendMessage(ErrorMessage(f'{command_first_word}未绑定任何命令，请联系开发者处理。'))
                            continue

                        none_doc = True  # 检查模块绑定的命令是否有文档
                        for func in module.match_list.get(msg.target.targetFrom):
                            if func.help_doc:
                                none_doc = False
                        if not none_doc:  # 如果有，送入命令解析
                            async def execute_submodule(msg: MessageSession, command_first_word, command_split):
                                try:
                                    command_parser = CommandParser(module, msg=msg, bind_prefix=command_first_word,
                                                                   command_prefixes=msg.prefixes)
                                    try:
                                        parsed_msg = command_parser.parse(msg.trigger_msg)  # 解析命令对应的子模块
                                        submodule = parsed_msg[0]
                                        msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
                                        Logger.debug(msg.parsed_msg)

                                        if submodule.required_superuser:
                                            if not msg.checkSuperUser():
                                                await msg.sendMessage('你没有使用该命令的权限。')
                                                return
                                        elif submodule.required_admin:
                                            if not await msg.checkPermission():
                                                await msg.sendMessage(
                                                    f'此命令仅能被该群组的管理员所使用，请联系管理员执行此命令。')
                                                return

                                        if not senderInfo.query.disable_typing:
                                            async with msg.Typing(msg):
                                                await parsed_msg[0].function(msg)  # 将msg传入下游模块
                                        else:
                                            await parsed_msg[0].function(msg)
                                        raise FinishedException(msg.sent)  # if not using msg.finish
                                    except InvalidCommandFormatError:
                                        await msg.sendMessage(f'语法错误。\n使用~help {command_first_word}查看帮助。')
                                        """if msg.options.get('typo_check', True):  # 判断是否开启错字检查
                                            nmsg, command_first_word, command_split = await typo_check(msg,
                                                                                                       display_prefix,
                                                                                                       modules,
                                                                                                       command_first_word,
                                                                                                       command_split)
                                            if nmsg is None:
                                                return ExecutionLockList.remove(msg)
                                            msg = nmsg
                                            await execute_submodule(msg, command_first_word, command_split)"""
                                        return
                                except InvalidHelpDocTypeError:
                                    Logger.error(traceback.format_exc())
                                    await msg.sendMessage(ErrorMessage(f'{command_first_word}模块的帮助信息有误，请联系开发者处理。'))
                                    return

                            await execute_submodule(msg, command_first_word, command_split)
                        else:  # 如果没有，直接传入下游模块
                            msg.parsed_msg = None
                            for func in module.match_list.set:
                                if not func.help_doc:
                                    if not senderInfo.query.disable_typing:
                                        async with msg.Typing(msg):
                                            await func.function(msg)  # 将msg传入下游模块
                                    else:
                                        await func.function(msg)
                                    raise FinishedException(msg.sent)  # if not using msg.finish
                    except ActionFailed:
                        ExecutionLockList.remove(msg)
                        await msg.sendMessage('消息发送失败，可能被风控，请稍后再试。')
                        continue

                    except FinishedException as e:
                        time_used = datetime.now() - time_start
                        Logger.info(f'Successfully finished session from {identify_str}, returns: {str(e)}. '
                                    f'Times take up: {str(time_used)}')
                        if msg.target.targetFrom != 'QQ|Guild' or command_first_word != 'module' and enable_tos:
                            await msg_counter(msg, msg.trigger_msg)
                        else:
                            Logger.debug(f'Tos is disabled, check the configuration is correct.')
                        ExecutionLockList.remove(msg)
                        if enable_analytics:
                            BotDBUtil.Analytics(msg).add(msg.trigger_msg, command_first_word, 'normal')
                        continue

                    except NoReportException as e:
                        Logger.error(traceback.format_exc())
                        ExecutionLockList.remove(msg)
                        await msg.sendMessage('执行命令时发生错误：\n' + str(e) + '\n此问题并非机器人程序错误（API请求出错等），'
                                                                        '请勿将此消息报告给机器人开发者。')
                        continue

                    except Exception as e:
                        Logger.error(traceback.format_exc())
                        ExecutionLockList.remove(msg)
                        await msg.sendMessage(ErrorMessage('执行命令时发生错误，请报告机器人开发者：\n' + str(e)))
                        continue
            ExecutionLockList.remove(msg)
            return msg
        if running_mention:
            if display.find('小可') != -1:
                if ExecutionLockList.check(msg):
                    return await msg.sendMessage('您先前的命令正在执行中。')

        for regex in modulesRegex:  # 遍历正则模块列表
            try:
                if regex in msg.enabled_modules:  # 如果模块已启用
                    regex_module = modulesRegex[regex]

                    if regex_module.required_superuser:
                        if not msg.checkSuperUser():
                            continue
                    elif regex_module.required_admin:
                        if not await msg.checkPermission():
                            continue

                    for rfunc in regex_module.match_list.set:  # 遍历正则模块的表达式
                        time_start = datetime.now()
                        try:
                            msg.matched_msg = False
                            matched = False
                            if rfunc.mode.upper() in ['M', 'MATCH']:
                                msg.matched_msg = re.match(rfunc.pattern, display, flags=rfunc.flags)
                                if msg.matched_msg is not None:
                                    matched = True
                            elif rfunc.mode.upper() in ['A', 'FINDALL']:
                                msg.matched_msg = re.findall(rfunc.pattern, display, flags=rfunc.flags)
                                if msg.matched_msg and msg.matched_msg is not None:
                                    matched = True

                            if matched:  # 如果匹配成功
                                if rfunc.logging:
                                    Logger.info(
                                        f'{identify_str} -> [Bot]: {display}')
                                if enable_tos and rfunc.show_typing:
                                    await temp_ban_check(msg)
                                if regex_module.required_superuser:
                                    if not msg.checkSuperUser():
                                        continue
                                elif regex_module.required_admin:
                                    if not await msg.checkPermission():
                                        continue
                                if not ExecutionLockList.check(msg):
                                    ExecutionLockList.add(msg)
                                else:
                                    return await msg.sendMessage('您有命令正在执行，请稍后再试。')
                                if rfunc.show_typing and not senderInfo.query.disable_typing:
                                    async with msg.Typing(msg):
                                        await rfunc.function(msg)  # 将msg传入下游模块
                                else:
                                    await rfunc.function(msg)  # 将msg传入下游模块
                                raise FinishedException(msg.sent)  # if not using msg.finish
                        except FinishedException as e:
                            time_used = datetime.now() - time_start
                            if rfunc.logging:
                                Logger.info(
                                    f'Successfully finished session from {identify_str}, returns: {str(e)}. '
                                    f'Times take up: {time_used}')
                            ExecutionLockList.remove(msg)

                            if enable_analytics and rfunc.show_typing:
                                BotDBUtil.Analytics(msg).add(msg.trigger_msg, regex, 'regex')

                            if enable_tos and rfunc.show_typing:
                                await msg_counter(msg, msg.trigger_msg)
                            else:
                                Logger.debug(f'Tos is disabled.')

                            continue

            except ActionFailed:
                ExecutionLockList.remove(msg)
                await msg.sendMessage('消息发送失败，可能被风控，请稍后再试。')
                continue

            ExecutionLockList.remove(msg)
        return msg
    except AbuseWarning as e:
        if enable_tos:
            await warn_target(msg, str(e))
            temp_ban_counter[msg.target.senderId] = {'count': 1,
                                                     'ts': datetime.now().timestamp()}
            return

    except WaitCancelException:  # 出现于等待被取消的情况
        Logger.warn('Waiting task cancelled by user.')

    except Exception:
        Logger.error(traceback.format_exc())
    ExecutionLockList.remove(msg)


async def typo_check(msg: MessageSession, display_prefix, modules, command_first_word, command_split):
    enabled_modules = []
    for m in msg.enabled_modules:
        if m in modules and isinstance(modules[m], Command):
            enabled_modules.append(m)
    match_close_module: list = difflib.get_close_matches(command_first_word, enabled_modules, 1, 0.6)
    if match_close_module:
        module = modules[match_close_module[0]]
        none_doc = True  # 检查模块绑定的命令是否有文档
        for func in module.match_list.get(msg.target.targetFrom):
            if func.help_doc is not None:
                none_doc = False
        len_command_split = len(command_split)
        if not none_doc and len_command_split > 1:
            get_submodules: List[CommandMeta] = module.match_list.get(msg.target.targetFrom)
            docs = {}  # 根据命令模板的空格数排序命令
            for func in get_submodules:
                help_doc: List[Template] = copy.deepcopy(func.help_doc)
                if not help_doc:
                    ...  # todo: ...此处应该有一个处理例外情况的逻辑

                for h_ in help_doc:
                    h_.args_ = [a for a in h_.args if isinstance(a, ArgumentPattern)]
                    if (len_args := len(h_.args)) not in docs:
                        docs[len_args] = [h_]
                    else:
                        docs[len_args].append(h_)

            if len_command_split - 1 > len(docs):  # 如果空格数远大于命令模板的空格数
                select_docs = docs[max(docs)]
            else:
                select_docs = docs[len_command_split - 1]  # 选择匹配的命令组
            match_close_command: list = difflib.get_close_matches(' '.join(command_split[1:]), templates_to_str(select_docs),
                                                                  1, 0.3)  # 进一步匹配命令
            if match_close_command:
                match_split = match_close_command[0]
                m_split_options = filter(None, re.split(r'(\[.*?])', match_split))  # 切割可选参数
                old_command_split = command_split.copy()
                del old_command_split[0]
                new_command_split = [match_close_module[0]]
                for m_ in m_split_options:
                    if m_.startswith('['):  # 如果是可选参数
                        m_split = m_.split(' ')  # 切割可选参数中的空格（说明存在多个子必须参数）
                        if len(m_split) > 1:
                            match_close_options = difflib.get_close_matches(m_split[0][1:], old_command_split, 1,
                                                                            0.3)  # 进一步匹配可选参数
                            if match_close_options:
                                position = old_command_split.index(match_close_options[0])  # 定位可选参数的位置
                                new_command_split.append(m_split[0][1:])  # 将可选参数插入到新命令列表中
                                new_command_split += old_command_split[position + 1: position + len(m_split)]
                                del old_command_split[position: position + len(m_split)]  # 删除原命令列表中的可选参数
                        else:
                            if m_split[0][1] == '<':
                                new_command_split.append(old_command_split[0])
                                del old_command_split[0]
                            else:
                                new_command_split.append(m_split[0][1:-1])
                    else:
                        m__ = filter(None, m_.split(' '))  # 必须参数
                        for mm in m__:
                            if len(old_command_split) > 0:
                                if mm.startswith('<'):
                                    new_command_split.append(old_command_split[0])
                                    del old_command_split[0]
                                else:
                                    match_close_args = difflib.get_close_matches(old_command_split[0], [mm], 1,
                                                                                 0.5)  # 进一步匹配参数
                                    if match_close_args:
                                        new_command_split.append(mm)
                                        del old_command_split[0]
                                    else:
                                        new_command_split.append(old_command_split[0])
                                        del old_command_split[0]
                            else:
                                new_command_split.append(mm)
                new_command_display = " ".join(new_command_split)
                if new_command_display != msg.trigger_msg:
                    wait_confirm = await msg.waitConfirm(
                        f'您是否想要输入{display_prefix}{new_command_display}？')
                    if wait_confirm:
                        command_split = new_command_split
                        command_first_word = new_command_split[0]
                        msg.trigger_msg = ' '.join(new_command_split)
                        return msg, command_first_word, command_split
            else:
                if len_command_split - 1 == 1:
                    new_command_display = f'{match_close_module[0]} {" ".join(command_split[1:])}'
                    if new_command_display != msg.trigger_msg:
                        wait_confirm = await msg.waitConfirm(
                            f'您是否想要输入{display_prefix}{new_command_display}？')
                        if wait_confirm:
                            command_split = [match_close_module[0]] + command_split[1:]
                            command_first_word = match_close_module[0]
                            msg.trigger_msg = ' '.join(command_split)
                            return msg, command_first_word, command_split

        else:
            new_command_display = f'{match_close_module[0] + (" " + " ".join(command_split[1:]) if len(command_split) > 1 else "")}'
            if new_command_display != msg.trigger_msg:
                wait_confirm = await msg.waitConfirm(
                    f'您是否想要输入{display_prefix}{new_command_display}？')
                if wait_confirm:
                    command_split = [match_close_module[0]]
                    command_first_word = match_close_module[0]
                    msg.trigger_msg = ' '.join(command_split)
                    return msg, command_first_word, command_split
    return None, None, None
