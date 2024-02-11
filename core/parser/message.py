import asyncio
import inspect
import re
import traceback
from datetime import datetime

from config import Config
from core.builtins import command_prefix, ExecutionLockList, ErrorMessage, MessageTaskManager, Url, Bot, \
    base_superuser_list
from core.exceptions import AbuseWarning, FinishedException, InvalidCommandFormatError, InvalidHelpDocTypeError, \
    WaitCancelException, NoReportException, SendMessageFailed
from core.loader import ModulesManager, current_unloaded_modules, err_modules
from core.logger import Logger
from core.parser.command import CommandParser
from core.tos import warn_target
from core.types import Module
from core.utils.message import remove_duplicate_space
from database import BotDBUtil

enable_tos = Config('enable_tos')
enable_analytics = Config('enable_analytics')
bug_report_targets = Config('bug_report_targets')

TOS_TEMPBAN_TIME = Config('tos_temp_ban_time', 300)

counter_same = {}  # 命令使用次数计数（重复使用单一命令）
counter_all = {}  # 命令使用次数计数（使用所有命令）

temp_ban_counter = {}  # 临时封禁计数


async def check_temp_ban(msg: Bot.MessageSession):
    is_temp_banned = temp_ban_counter.get(msg.target.sender_id)
    if is_temp_banned:
        ban_time = datetime.now().timestamp() - is_temp_banned['ts']
        return int(TOS_TEMPBAN_TIME - ban_time)
    else:
        return False

async def remove_temp_ban(msg: Bot.MessageSession):
    if await check_temp_ban(msg.target.sender_id):
        del temp_ban_counter[msg.target.sender_id]


async def tos_msg_counter(msg: Bot.MessageSession, command: str):
    same = counter_same.get(msg.target.sender_id)
    if not same or datetime.now().timestamp() - same['ts'] > 300 or same['command'] != command:
        # 检查是否滥用（5分钟内重复使用同一命令10条）
        counter_same[msg.target.sender_id] = {'command': command, 'count': 1,
                                              'ts': datetime.now().timestamp()}
    else:
        same['count'] += 1
        if same['count'] > 10:
            raise AbuseWarning(msg.locale.t("tos.reason.cooldown"))
    all_ = counter_all.get(msg.target.sender_id)
    if not all_ or datetime.now().timestamp() - all_['ts'] > 300:  # 检查是否滥用（5分钟内使用20条命令）
        counter_all[msg.target.sender_id] = {'count': 1,
                                             'ts': datetime.now().timestamp()}
    else:
        all_['count'] += 1
        if all_['count'] > 20:
            raise AbuseWarning(msg.locale.t("tos.reason.abuse"))


async def temp_ban_check(msg: Bot.MessageSession):
    is_temp_banned = temp_ban_counter.get(msg.target.sender_id)
    is_superuser = msg.check_super_user()
    if is_temp_banned and not is_superuser:
        ban_time = datetime.now().timestamp() - is_temp_banned['ts']
        if ban_time < TOS_TEMPBAN_TIME:
            if is_temp_banned['count'] < 2:
                is_temp_banned['count'] += 1
                await msg.finish(msg.locale.t("tos.tempbanned", ban_time=int(TOS_TEMPBAN_TIME - ban_time)))
            elif is_temp_banned['count'] <= 5:
                is_temp_banned['count'] += 1
                await msg.finish(msg.locale.t("tos.tempbanned.warning", ban_time=int(TOS_TEMPBAN_TIME - ban_time)))
            else:
                raise AbuseWarning(msg.locale.t("tos.reason.bypass"))


async def parser(msg: Bot.MessageSession, require_enable_modules: bool = True, prefix: list = None,
                 running_mention: bool = False):
    """
    接收消息必经的预处理器
    :param msg: 从监听器接收到的dict，该dict将会经过此预处理器传入下游
    :param require_enable_modules: 是否需要检查模块是否已启用
    :param prefix: 使用的命令前缀。如果为None，则使用默认的命令前缀，存在''值的情况下则代表无需命令前缀
    :param running_mention: 消息内若包含机器人名称，则检查是否有命令正在运行
    :return: 无返回
    """
    identify_str = f'[{msg.target.sender_id}{f" ({msg.target.target_id})" if msg.target.target_from != msg.target.sender_from else ""}]'
    # Logger.info(f'{identify_str} -> [Bot]: {display}')
    try:
        asyncio.create_task(MessageTaskManager.check(msg))
        modules = ModulesManager.return_modules_list(msg.target.target_from)

        msg.trigger_msg = remove_duplicate_space(msg.as_display())  # 将消息转换为一般显示形式
        if len(msg.trigger_msg) == 0:
            return
        msg.target.sender_info = BotDBUtil.SenderInfo(msg.target.sender_id)
        if msg.target.sender_info.query.isInBlockList and not msg.target.sender_info.query.isInAllowList and not msg.target.sender_info.query.isSuperUser \
                or msg.target.sender_id in msg.options.get('ban', []):
            return
        msg.prefixes = command_prefix.copy()  # 复制一份作为基础命令前缀
        get_custom_alias = msg.options.get('command_alias')
        if get_custom_alias:
            get_display_alias = get_custom_alias.get(msg.trigger_msg)
            if get_display_alias:
                msg.trigger_msg = get_display_alias
        get_custom_prefix = msg.options.get('command_prefix')  # 获取自定义命令前缀
        if get_custom_prefix:
            msg.prefixes = get_custom_prefix + msg.prefixes  # 混合

        disable_prefix = False
        if prefix:  # 如果上游指定了命令前缀，则使用指定的命令前缀
            if '' in prefix:
                disable_prefix = True
            msg.prefixes.clear()
            msg.prefixes.extend(prefix)
        display_prefix = ''
        in_prefix_list = False
        for cp in msg.prefixes:  # 判断是否在命令前缀列表中
            if msg.trigger_msg.startswith(cp):
                display_prefix = cp
                in_prefix_list = True
                break

        if in_prefix_list or disable_prefix:  # 检查消息前缀
            if len(msg.trigger_msg) <= 1 or msg.trigger_msg[:2] == '~~':  # 排除 ~~xxx~~ 的情况
                return
            if in_prefix_list:  # 如果在命令前缀列表中，则将此命令前缀移动到列表首位
                msg.prefixes.remove(display_prefix)
                msg.prefixes.insert(0, display_prefix)

            Logger.info(
                f'{identify_str} -> [Bot]: {msg.trigger_msg}')

            if disable_prefix and not in_prefix_list:
                command = msg.trigger_msg
            else:
                command = msg.trigger_msg[len(display_prefix):]

            if not ExecutionLockList.check(msg):  # 加锁
                ExecutionLockList.add(msg)
            else:
                return await msg.send_message(msg.locale.t("parser.command.running.prompt"))

            no_alias = False
            for moduleName in modules:
                if command.startswith(moduleName):  # 判断此命令是否匹配一个实际的模块
                    no_alias = True
            if not no_alias:
                for um in current_unloaded_modules:
                    if command.startswith(um):
                        no_alias = True
            if not no_alias:
                for em in err_modules:
                    if command.startswith(em):
                        no_alias = True
            if not no_alias:  # 如果没有匹配到模块，则判断是否匹配命令别名
                alias_list = []
                for alias in ModulesManager.modules_aliases:
                    if command.startswith(alias) and not command.startswith(ModulesManager.modules_aliases[alias]):
                        alias_list.append(alias)
                if alias_list:
                    max_ = max(alias_list, key=len)
                    command = command.replace(max_, ModulesManager.modules_aliases[max_], 1)
            command_split: list = command.split(' ')  # 切割消息
            msg.trigger_msg = command  # 触发该命令的消息，去除消息前缀
            command_first_word = command_split[0].lower()

            sudo = False
            mute = False
            if command_first_word == 'mute':
                mute = True
            if command_first_word == 'sudo':
                if not msg.check_super_user():
                    return await msg.send_message(msg.locale.t("parser.superuser.permission.denied"))
                sudo = True
                del command_split[0]
                command_first_word = command_split[0].lower()
                msg.trigger_msg = ' '.join(command_split)

            in_mute = msg.muted
            if in_mute and not mute:
                return

            if command_first_word in modules:  # 检查触发命令是否在模块列表中
                time_start = datetime.now()
                try:
                    if enable_tos:
                        await temp_ban_check(msg)

                    module: Module = modules[command_first_word]
                    if not module.command_list.set:  # 如果没有可用的命令，则展示模块简介
                        if module.desc:
                            desc = msg.locale.t("parser.module.desc", desc=msg.locale.tl_str(module.desc))

                            if command_first_word not in msg.enabled_modules:
                                desc += '\n' + msg.locale.t("parser.module.disabled.prompt", module=command_first_word,
                                                            prefix=msg.prefixes[0])
                            await msg.send_message(desc)
                        else:
                            await msg.send_message(ErrorMessage(msg.locale.t("error.module.unbound",
                                                                             module=command_first_word)))
                        return

                    if module.required_base_superuser:
                        if msg.target.sender_id not in base_superuser_list:
                            await msg.send_message(msg.locale.t("parser.superuser.permission.denied"))
                            return
                    elif module.required_superuser:
                        if not msg.check_super_user():
                            await msg.send_message(msg.locale.t("parser.superuser.permission.denied"))
                            return
                    elif not module.base:
                        if command_first_word not in msg.enabled_modules and not sudo and require_enable_modules:  # 若未开启
                            await msg.send_message(
                                msg.locale.t("parser.module.disabled.prompt", module=command_first_word,
                                             prefix=msg.prefixes[0]))
                            return
                    elif module.required_admin:
                        if not await msg.check_permission():
                            await msg.send_message(msg.locale.t("parser.admin.module.permission.denied",
                                                                module=command_first_word))
                            return

                    none_doc = True  # 检查模块绑定的命令是否有文档
                    for func in module.command_list.get(msg.target.target_from):
                        if func.help_doc:
                            none_doc = False
                    if not none_doc:  # 如果有，送入命令解析
                        async def execute_submodule(msg: Bot.MessageSession, command_first_word, command_split):
                            try:
                                command_parser = CommandParser(module, msg=msg, bind_prefix=command_first_word,
                                                               command_prefixes=msg.prefixes)
                                try:
                                    parsed_msg = command_parser.parse(msg.trigger_msg)  # 解析命令对应的子模块
                                    submodule = parsed_msg[0]
                                    msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
                                    Logger.debug(msg.parsed_msg)

                                    if submodule.required_base_superuser:
                                        if msg.target.sender_id not in base_superuser_list:
                                            await msg.send_message(msg.locale.t("parser.superuser.permission.denied"))
                                            return
                                    elif submodule.required_superuser:
                                        if not msg.check_super_user():
                                            await msg.send_message(msg.locale.t("parser.superuser.permission.denied"))
                                            return
                                    elif submodule.required_admin:
                                        if not await msg.check_permission():
                                            await msg.send_message(
                                                msg.locale.t("parser.admin.submodule.permission.denied"))
                                            return

                                    if msg.target.target_from in submodule.exclude_from or \
                                        ('*' not in submodule.available_for and
                                         msg.target.target_from not in submodule.available_for):
                                        raise InvalidCommandFormatError

                                    kwargs = {}
                                    func_params = inspect.signature(submodule.function).parameters
                                    if len(func_params) > 1 and msg.parsed_msg:
                                        parsed_msg_ = msg.parsed_msg.copy()
                                        for param_name, param_obj in func_params.items():
                                            if param_obj.annotation == Bot.MessageSession:
                                                kwargs[param_name] = msg
                                            param_name_ = param_name
                                            if (param_name__ := f'<{param_name}>') in parsed_msg_:
                                                param_name_ = param_name__

                                            if param_name_ in parsed_msg_:
                                                kwargs[param_name] = parsed_msg_[param_name_]
                                                try:
                                                    if param_obj.annotation == int:
                                                        kwargs[param_name] = int(parsed_msg_[param_name_])
                                                    elif param_obj.annotation == float:
                                                        kwargs[param_name] = float(parsed_msg_[param_name_])
                                                    elif param_obj.annotation == bool:
                                                        kwargs[param_name] = bool(parsed_msg_[param_name_])
                                                    del parsed_msg_[param_name_]
                                                except (KeyError, ValueError):
                                                    raise InvalidCommandFormatError
                                            else:
                                                if param_name_ not in kwargs:
                                                    if param_obj.default is not inspect.Parameter.empty:
                                                        kwargs[param_name_] = param_obj.default
                                                    else:
                                                        kwargs[param_name_] = None

                                    else:
                                        kwargs[func_params[list(func_params.keys())[0]].name] = msg

                                    if not msg.target.sender_info.query.disable_typing:
                                        async with msg.Typing(msg):
                                            await parsed_msg[0].function(**kwargs)  # 将msg传入下游模块
                                    else:
                                        await parsed_msg[0].function(**kwargs)
                                    raise FinishedException(msg.sent)  # if not using msg.finish
                                except InvalidCommandFormatError:
                                    await msg.send_message(msg.locale.t("parser.command.format.invalid",
                                                                        module=command_first_word,
                                                                        prefix=msg.prefixes[0]))
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
                                await msg.send_message(
                                    ErrorMessage(msg.locale.t("error.module.helpdoc.invalid",
                                                              module=command_first_word)))
                                return

                        await execute_submodule(msg, command_first_word, command_split)
                    else:  # 如果没有，直接传入下游模块
                        msg.parsed_msg = None
                        for func in module.command_list.set:
                            if not func.help_doc:
                                if not msg.target.sender_info.query.disable_typing:
                                    async with msg.Typing(msg):
                                        await func.function(msg)  # 将msg传入下游模块
                                else:
                                    await func.function(msg)
                                raise FinishedException(msg.sent)  # if not using msg.finish
                except SendMessageFailed:
                    if msg.target.target_from == 'QQ|Group':
                        await msg.call_api('send_group_msg', group_id=msg.session.target,
                                           message=f'[CQ:poke,qq={Config("qq_account")}]')
                    await msg.send_message(msg.locale.t("error.message.limited"))

                except FinishedException as e:
                    time_used = datetime.now() - time_start
                    Logger.info(f'Successfully finished session from {identify_str}, returns: {str(e)}. '
                                f'Times take up: {str(time_used)}')
                    if (msg.target.target_from != 'QQ|Guild' or command_first_word != 'module') and enable_tos:
                        await tos_msg_counter(msg, msg.trigger_msg)
                    else:
                        Logger.debug(f'Tos is disabled, check the configuration if it is not work as expected.')
                    if enable_analytics:
                        BotDBUtil.Analytics(msg).add(msg.trigger_msg, command_first_word, 'normal')

                except AbuseWarning as e:
                    if enable_tos and Config('tos_warning_counts', 5) >= 1:
                        await warn_target(msg, str(e))
                        temp_ban_counter[msg.target.sender_id] = {'count': 1,
                                                                  'ts': datetime.now().timestamp()}
                    else:
                        await msg.send_message(msg.locale.t("error.prompt.noreport", detail=e))

                except NoReportException as e:
                    Logger.error(traceback.format_exc())
                    err_msg = msg.locale.tl_str(str(e))
                    await msg.send_message(msg.locale.t("error.prompt.noreport", detail=err_msg))

                except Exception as e:
                    tb = traceback.format_exc()
                    Logger.error(tb)
                    errmsg = msg.locale.t('error.prompt', detail=str(e))
                    if Config('bug_report_url'):
                        errmsg += '\n' + msg.locale.t('error.prompt.address', url=str(Url(Config('bug_report_url'))))
                    await msg.send_message(errmsg)
                    if bug_report_targets:
                        for target in bug_report_targets:
                            if f := await Bot.FetchTarget.fetch_target(target):
                                await f.send_direct_message(
                                    msg.locale.t('error.message.report', module=msg.trigger_msg) + tb)
            if command_first_word in current_unloaded_modules and msg.check_super_user():
                await msg.send_message(
                    msg.locale.t('parser.module.unloaded', module=command_first_word, prefix=msg.prefixes[0]))
            elif command_first_word in err_modules:
                await msg.send_message(msg.locale.t('error.module.unloaded', module=command_first_word))

            return msg
        if msg.muted:
            return
        if running_mention:
            if msg.trigger_msg.find('小可') != -1:
                if ExecutionLockList.check(msg):
                    return await msg.send_message(msg.locale.t('parser.command.running.prompt2'))

        for m in modules:  # 遍历模块
            try:
                if m in msg.enabled_modules and modules[m].regex_list.set:  # 如果模块已启用
                    regex_module = modules[m]

                    if regex_module.required_base_superuser:
                        if msg.target.sender_id not in base_superuser_list:
                            continue
                    elif regex_module.required_superuser:
                        if not msg.check_super_user():
                            continue
                    elif regex_module.required_admin:
                        if not await msg.check_permission():
                            continue

                    if msg.target.target_from in regex_module.exclude_from or \
                        ('*' not in regex_module.available_for and
                         msg.target.target_from not in regex_module.available_for):
                        continue

                    for rfunc in regex_module.regex_list.set:  # 遍历正则模块的表达式
                        time_start = datetime.now()
                        try:
                            msg.matched_msg = False
                            matched = False
                            if rfunc.mode.upper() in ['M', 'MATCH']:
                                msg.matched_msg = re.match(rfunc.pattern, msg.trigger_msg, flags=rfunc.flags)
                                if msg.matched_msg:
                                    matched = True
                            elif rfunc.mode.upper() in ['A', 'FINDALL']:
                                msg.matched_msg = re.findall(rfunc.pattern, msg.trigger_msg, flags=rfunc.flags)
                                if msg.matched_msg:
                                    matched = True

                            if matched and not (msg.target.target_from in regex_module.exclude_from or
                                                ('*' not in regex_module.available_for and
                                                 msg.target.target_from not in regex_module.available_for)):  # 如果匹配成功
                                if rfunc.logging:
                                    Logger.info(
                                        f'{identify_str} -> [Bot]: {msg.trigger_msg}')
                                if enable_tos and rfunc.show_typing:
                                    await temp_ban_check(msg)
                                if rfunc.required_superuser:
                                    if not msg.check_super_user():
                                        continue
                                elif rfunc.required_admin:
                                    if not await msg.check_permission():
                                        continue
                                if not ExecutionLockList.check(msg):
                                    ExecutionLockList.add(msg)
                                else:
                                    return await msg.send_message(msg.locale.t("parser.command.running.prompt"))
                                if rfunc.show_typing and not msg.target.sender_info.query.disable_typing:
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

                            if enable_analytics and rfunc.show_typing:
                                BotDBUtil.Analytics(msg).add(msg.trigger_msg, m, 'regex')

                            if enable_tos and rfunc.show_typing:
                                await tos_msg_counter(msg, msg.trigger_msg)
                            else:
                                Logger.debug(f'Tos is disabled, check the configuration if it is not work as expected.')

                            continue
                        except NoReportException as e:
                            Logger.error(traceback.format_exc())
                            err_msg = msg.locale.tl_str(str(e))
                            await msg.send_message(msg.locale.t("error.prompt.noreport", detail=err_msg))

                        except AbuseWarning as e:
                            if enable_tos and Config('tos_warning_counts', 5) >= 1:
                                await warn_target(msg, str(e))
                                temp_ban_counter[msg.target.sender_id] = {'count': 1,
                                                                          'ts': datetime.now().timestamp()}
                            else:
                                await msg.send_message(msg.locale.t("error.prompt.noreport", detail=str(e)))

                        except Exception as e:
                            tb = traceback.format_exc()
                            Logger.error(tb)
                            errmsg = msg.locale.t('error.prompt', detail=str(e))
                            if Config('bug_report_url'):
                                errmsg += '\n' + msg.locale.t('error.prompt.address',
                                                              url=str(Url(Config('bug_report_url'))))
                            await msg.send_message(errmsg)
                            if bug_report_targets:
                                for target in bug_report_targets:
                                    if f := await Bot.FetchTarget.fetch_target(target):
                                        await f.send_direct_message(
                                            msg.locale.t('error.message.report', module=msg.trigger_msg) + tb)
                        finally:
                            ExecutionLockList.remove(msg)

            except SendMessageFailed:
                if msg.target.target_from == 'QQ|Group':
                    await msg.call_api('send_group_msg', group_id=msg.session.target,
                                       message=f'[CQ:poke,qq={Config("qq_account")}]')
                await msg.send_message((msg.locale.t("error.message.limited")))
                continue
        return msg

    except WaitCancelException:  # 出现于等待被取消的情况
        Logger.warn('Waiting task cancelled by user.')

    except Exception:
        Logger.error(traceback.format_exc())
    finally:
        ExecutionLockList.remove(msg)


"""async def typo_check(msg: MessageSession, display_prefix, modules, command_first_word, command_split):
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
            match_close_command: list = difflib.get_close_matches(' '.join(command_split[1:]),
                                                                  templates_to_str(select_docs),
                                                                  1, 0.3)  # 进一步匹配命令
            if match_close_command:
                match_split = match_close_command[0]
                m_split_options = filter(None, re.split(r'(\\[.*?])', match_split))  # 切割可选参数
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
                        f'你是否想要输入{display_prefix}{new_command_display}？')
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
                            f'你是否想要输入{display_prefix}{new_command_display}？')
                        if wait_confirm:
                            command_split = [match_close_module[0]] + command_split[1:]
                            command_first_word = match_close_module[0]
                            msg.trigger_msg = ' '.join(command_split)
                            return msg, command_first_word, command_split

        else:
            new_command_display = f'{match_close_module[0] + (" " + " ".join(command_split[1:]) if len(command_split) > 1 else "")}'
            if new_command_display != msg.trigger_msg:
                wait_confirm = await msg.waitConfirm(
                    f'你是否想要输入{display_prefix}{new_command_display}？')
                if wait_confirm:
                    command_split = [match_close_module[0]]
                    command_first_word = match_close_module[0]
                    msg.trigger_msg = ' '.join(command_split)
                    return msg, command_first_word, command_split
    return None, None, None
"""
