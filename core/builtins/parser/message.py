import copy
import difflib
import inspect
import re
import traceback
from datetime import datetime
from string import Template as stringTemplate
from typing import List, TYPE_CHECKING

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.internal import Plain, I18NContext
from core.builtins.parser.args import ArgumentPattern, Template as argsTemplate, templates_to_str
from core.builtins.parser.command import CommandParser
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.config import Config
from core.constants.default import bug_report_url_default, ignored_sender_default
from core.constants.exceptions import AbuseWarning, FinishedException, InvalidCommandFormatError, \
    InvalidHelpDocTypeError, \
    WaitCancelException, NoReportException, SendMessageFailed
from core.constants.info import Info
from core.database.models import AnalyticsData
from core.exports import exports
from core.loader import ModulesManager
from core.logger import Logger
from core.tos import abuse_warn_target
from core.types import Module, Param
from core.types.module.component_meta import CommandMeta
from core.utils.message import normalize_space
from core.utils.temp import TempCounter

if TYPE_CHECKING:
    from core.builtins.bot import Bot

ignored_sender = Config("ignored_sender", ignored_sender_default)

enable_tos = Config("enable_tos", True)
enable_analytics = Config("enable_analytics", True)
report_targets = Config("report_targets", [])
enable_module_invalid_prompt = Config("enable_module_invalid_prompt", False)
TOS_TEMPBAN_TIME = Config("tos_temp_ban_time", 300) if Config("tos_temp_ban_time", 300) > 0 else 300
bug_report_url = Config("bug_report_url", bug_report_url_default)

typo_check_module_score = Config("typo_check_module_score", 0.6)
typo_check_command_score = Config("typo_check_command_score", 0.3)
typo_check_args_score = Config("typo_check_args_score", 0.5)
typo_check_options_score = Config("typo_check_options_score", 0.3)

counter_same = {}  # 命令使用次数计数（重复使用单一命令）
counter_all = {}  # 命令使用次数计数（使用所有命令）

temp_ban_counter = {}  # 临时封禁计数
cooldown_counter = {}  # 冷却计数

match_hash_cache = {}


async def check_temp_ban(target):
    is_temp_banned = temp_ban_counter.get(target)
    if is_temp_banned:
        ban_time = datetime.now().timestamp() - is_temp_banned["ts"]
        ban_time_remain = int(TOS_TEMPBAN_TIME - ban_time)
        if ban_time_remain > 0:
            return ban_time_remain
    return False


async def remove_temp_ban(target):
    if await check_temp_ban(target):
        del temp_ban_counter[target]


async def parser(msg: "Bot.MessageSession"):
    """
    接收消息必经的预处理器。

    :param msg: 从监听器接收到的MessageSession，该MessageSession将会经过此预处理器传入下游。
    """
    await msg.session_info.refresh_info()
    identify_str = f"[{msg.session_info.sender_id} ({msg.session_info.target_id})]"
    # Logger.info(f"{identify_str} -> [Bot]: {display}")

    if msg.session_info.sender_id in ignored_sender:
        return

    try:
        await SessionTaskManager.check(msg)
        modules = ModulesManager.return_modules_list(msg.session_info.target_from, msg.session_info.client_name)

        msg.trigger_msg = normalize_space(msg.as_display())  # 将消息转换为一般显示形式
        if len(msg.trigger_msg) == 0:
            return
        if msg.session_info.sender_info.blocked and \
                not (msg.session_info.sender_info.trusted or msg.session_info.sender_info.superuser):
            return
        if msg.session_info.sender_id in msg.session_info.banned_users and not msg.session_info.superuser:
            return

        disable_prefix, in_prefix_list = _get_prefixes(msg)

        if in_prefix_list or disable_prefix:  # 检查消息前缀
            Logger.info(
                f"{identify_str} -> [Bot]: {msg.trigger_msg}")
            command_first_word = await _process_command(msg, modules, disable_prefix, in_prefix_list)
            if command_first_word:
                if not ExecutionLockList.check(msg):  # 加锁
                    ExecutionLockList.add(msg)
                else:
                    await msg.send_message(I18NContext("parser.command.running.prompt"))
                    return

            if msg.session_info.muted and command_first_word != "mute":  # 检查机器人在会话中是否被禁言
                return

            if command_first_word in modules:  # 检查触发命令是否在模块列表中
                if modules[command_first_word]._db_load:
                    await _execute_module(msg, modules, command_first_word, identify_str)
                else:
                    await msg.send_message(I18NContext("parser.module.unloaded", module=command_first_word))
            elif msg.session_info.sender_info.sender_data.get("typo_check", True):
                new_msg, new_command_first_word, confirmed = await _command_typo_check(msg, modules, command_first_word)
                if new_msg:
                    if modules[new_command_first_word]._db_load:
                        await _execute_module(new_msg, modules, new_command_first_word, identify_str)
                    else:
                        await msg.send_message(I18NContext("parser.module.unloaded", module=new_command_first_word))
                elif enable_module_invalid_prompt and not confirmed:
                    await msg.send_message(I18NContext("parser.command.invalid.module", prefix=msg.session_info.prefixes[0]))
            elif enable_module_invalid_prompt:
                await msg.send_message(I18NContext("parser.command.invalid.module", prefix=msg.session_info.prefixes[0]))

            return msg

        # 检查正则
        if msg.session_info.muted:
            return
        if msg.session_info.running_mention:
            if msg.trigger_msg.lower().find(msg.session_info.bot_name.lower()) != -1:
                if ExecutionLockList.check(msg):
                    return await msg.send_message(I18NContext("parser.command.running.prompt2"))

        await _execute_regex(msg, modules, identify_str)
        return msg

    except WaitCancelException:  # 出现于等待被取消的情况
        Logger.warning("Waiting task cancelled by user.")

    except Exception:
        Logger.exception()
    finally:
        await msg.end_typing()
        ExecutionLockList.remove(msg)
        TempCounter.add()


def _transform_alias(msg, command: str):
    aliases = dict(msg.session_info.target_info.target_data.get("command_alias", {}).items())
    command_split = msg.trigger_msg.split(" ")  # 切割消息
    for pattern, replacement in aliases.items():
        if re.search(r"\${[^}]*}", pattern):
            # 使用正则表达式匹配并分隔多个连在一起的占位符
            pattern = re.sub(r"(\$\{\w+})(?=\$\{\w+})", r"\1 ", pattern)
            # 匹配占位符
            pattern_placeholders = re.findall(r"\$\{([^{}$]+)}", pattern)

            regex_pattern = re.escape(pattern)
            for placeholder in pattern_placeholders:
                regex_pattern = regex_pattern.replace(re.escape(f"${{{placeholder}}}"), r"(\S+)")  # 匹配非空格字符

            match = re.match(regex_pattern, command)
            if match:
                groups = match.groups()
                placeholder_dict = {placeholder: groups[i] for i,
                                    placeholder in enumerate(pattern_placeholders) if i < len(groups)}
                result = stringTemplate(replacement).safe_substitute(placeholder_dict)

                Logger.debug(msg.session_info.prefixes[0] + result)
                return msg.session_info.prefixes[0] + result
        elif command_split[0] == pattern:
            # 旧语法兼容
            command_split[0] = msg.session_info.prefixes[0] + replacement  # 将自定义别名替换为命令
            Logger.debug(" ".join(command_split))
            return " ".join(command_split)  # 重新连接消息
        else:
            pass

    return command


def _get_prefixes(msg: "Bot.MessageSession"):
    if msg.session_info.target_info.target_data.get("command_alias"):
        msg.trigger_msg = _transform_alias(msg, msg.trigger_msg)  # 将自定义别名替换为命令

    disable_prefix = False
    if msg.session_info.prefixes:  # 如果上游指定了命令前缀，则使用指定的命令前缀
        if "" in msg.session_info.prefixes:
            disable_prefix = True
    display_prefix = ""
    in_prefix_list = False
    for cp in msg.session_info.prefixes:  # 判断是否在命令前缀列表中
        if msg.trigger_msg.startswith(cp):
            display_prefix = cp
            in_prefix_list = True
            break
    if in_prefix_list or disable_prefix:  # 检查消息前缀
        if len(msg.trigger_msg) <= 1 or msg.trigger_msg[:2] == "~~":  # 排除 ~~xxx~~ 的情况
            return False, False, ""
        if in_prefix_list:  # 如果在命令前缀列表中，则将此命令前缀移动到列表首位
            msg.session_info.prefixes.remove(display_prefix)
            msg.session_info.prefixes.insert(0, display_prefix)

    return disable_prefix, in_prefix_list


async def _process_command(msg: "Bot.MessageSession", modules, disable_prefix, in_prefix_list):
    if disable_prefix and not in_prefix_list:
        command = msg.trigger_msg
    else:
        command = msg.trigger_msg[len(msg.session_info.prefixes[0]):]

    command = command.strip()
    command_split: list = command.split(" ")  # 切割消息

    not_alias = False
    cm = ""
    for module_name in modules:
        if command_split[0] == module_name:  # 判断此命令是否匹配一个实际的模块
            not_alias = True
            cm = module_name
            break

    alias_list = []
    for alias, _ in ModulesManager.modules_aliases.items():
        alias_words = alias.split(" ")
        cmd_words = command.split(" ")

        if not not_alias:
            if cmd_words[:len(alias_words)] == alias_words:
                alias_list.append(alias)
        else:
            if alias.startswith(cm):
                if cmd_words[:len(alias_words)] == alias_words:
                    alias_list.append(alias)

    if alias_list:
        max_alias = max(alias_list, key=len)
        real_name = ModulesManager.modules_aliases[max_alias]
        command_words = command.split(" ")
        command_words = real_name.split(" ") + command_words[len(max_alias.split(" ")):]
        command = " ".join(command_words)

    msg.trigger_msg = command
    return command.split(" ")[0]


async def _execute_module(msg: "Bot.MessageSession", modules, command_first_word, identify_str):
    time_start = datetime.now()
    bot: "Bot" = exports["Bot"]
    try:
        await _check_target_cooldown(msg)
        if enable_tos:
            await _check_temp_ban(msg)

        module: Module = modules[command_first_word]
        if not module.command_list.set:  # 如果没有可用的命令，则展示模块简介
            if module.desc:
                desc = [I18NContext("parser.module.desc", desc=msg.session_info.locale.t_str(module.desc))]
                if command_first_word not in msg.session_info.enabled_modules:
                    desc.append(
                        I18NContext(
                            "parser.module.disabled.prompt",
                            module=command_first_word,
                            prefix=msg.session_info.prefixes[0]))
                await msg.send_message(desc)
            else:
                await msg.send_message(I18NContext("error.module.unbound", module=command_first_word))
            return

        if module.required_base_superuser:
            if msg.session_info.sender_id not in bot.base_superuser_list:
                await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                return
        elif module.required_superuser:
            if not msg.check_super_user():
                await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                return
        elif not module.base:
            if command_first_word not in msg.session_info.enabled_modules and msg.session_info.require_enable_modules:  # 若未开启
                await msg.send_message(I18NContext("parser.module.disabled.prompt", module=command_first_word,
                                                   prefix=msg.session_info.prefixes[0]))
                if await msg.check_permission():
                    if await msg.wait_confirm(I18NContext("parser.module.disabled.to_enable")):
                        await msg.session_info.target_info.config_module(command_first_word)
                        await msg.send_message(
                            I18NContext("core.message.module.enable.success", module=command_first_word))
                    else:
                        return
                else:
                    return
        elif module.required_admin:
            if not await msg.check_permission():
                await msg.send_message(I18NContext("parser.admin.module.permission.denied", module=command_first_word))
                return

        if not module.base:
            if enable_tos:  # 检查TOS是否滥用命令
                await _tos_msg_counter(msg, msg.trigger_msg)
            else:
                Logger.debug("Tos is disabled, check the configuration if it is not work as expected.")

        none_templates = True  # 检查模块绑定的命令是否有模板
        for func in module.command_list.get(msg.session_info.target_from):
            if func.command_template:
                none_templates = False
        if not none_templates:  # 如果有，送入命令解析
            await _execute_module_command(msg, module, command_first_word)
        else:  # 如果没有，直接传入下游模块
            msg.parsed_msg = None
            for func in module.command_list.set:
                if not func.command_template:
                    if msg.session_info.sender_info.sender_data.get("typing_prompt", True):
                        await msg.start_typing()
                    await func.function(msg)  # 将msg传入下游模块

                    raise FinishedException(msg.sent)  # if not using msg.finish

        if msg.session_info.sender_info.sender_data.get("typo_check", True):  # 判断是否开启错字检查
            new_msg, new_command_first_word, confirmed = await _command_typo_check(msg, modules, command_first_word)
            if new_msg:
                if modules[new_command_first_word]._db_load:
                    await _execute_module(new_msg, modules, new_command_first_word, identify_str)
                else:
                    await msg.send_message(I18NContext("parser.module.unloaded", module=new_command_first_word))
            elif not confirmed:
                await msg.send_message(I18NContext("parser.command.invalid.format",
                                                   module=command_first_word,
                                                   prefix=msg.session_info.prefixes[0]))
    except SendMessageFailed:
        await _process_send_message_failed(msg)

    except FinishedException as e:

        time_used = datetime.now() - time_start
        Logger.success(f"Successfully finished session from {identify_str}, returns: {str(e)}. "
                       f"Times take up: {str(time_used)}")
        Info.command_parsed += 1
        if enable_analytics:
            await AnalyticsData.create(target_id=msg.session_info.target_id,
                                       sender_id=msg.session_info.sender_id,
                                       command=msg.trigger_msg,
                                       module_name=command_first_word,
                                       module_type="normal")
    except AbuseWarning as e:
        await _process_tos_abuse_warning(msg, e)

    except NoReportException as e:
        await _process_noreport_exception(msg, e)

    except Exception as e:
        await _process_exception(msg, e)
    finally:
        await msg.end_typing()
        ExecutionLockList.remove(msg)


async def _execute_regex(msg: "Bot.MessageSession", modules, identify_str):
    bot: "Bot" = exports["Bot"]
    for m in modules:  # 遍历模块
        try:
            if m in msg.session_info.enabled_modules and modules[m].regex_list.set:  # 如果模块已启用
                regex_module: Module = modules[m]

                if regex_module.required_base_superuser:
                    if msg.session_info.sender_id not in bot.base_superuser_list:
                        continue
                elif regex_module.required_superuser:
                    if not msg.check_super_user():
                        continue
                elif regex_module.required_admin:
                    if not await msg.check_permission():
                        continue

                if not regex_module.load or \
                    msg.session_info.target_from in regex_module.exclude_from or \
                    msg.session_info.client_name in regex_module.exclude_from or \
                    ("*" not in regex_module.available_for and
                     msg.session_info.target_from not in regex_module.available_for and
                     msg.session_info.client_name not in regex_module.available_for):
                    continue

                for rfunc in regex_module.regex_list.set:  # 遍历正则模块的表达式
                    time_start = datetime.now()
                    matched = False
                    _typing = False
                    try:
                        matched_hash = 0
                        trigger_msg = msg.as_display(text_only=rfunc.text_only, element_filter=rfunc.element_filter)
                        if rfunc.mode.upper() in ["M", "MATCH"]:
                            msg.matched_msg = re.match(rfunc.pattern, trigger_msg, flags=rfunc.flags)
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg.groups())
                        elif rfunc.mode.upper() in ["A", "FINDALL"]:
                            msg.matched_msg = re.findall(rfunc.pattern, trigger_msg, flags=rfunc.flags)
                            msg.matched_msg = tuple(set(msg.matched_msg))
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg)

                        if matched and regex_module.load and not (
                            msg.session_info.target_from in regex_module.exclude_from or
                            msg.session_info.client_name in regex_module.exclude_from or
                            ("*" not in regex_module.available_for and
                             msg.session_info.target_from not in regex_module.available_for and
                             msg.session_info.client_name not in regex_module.available_for)):  # 如果匹配成功

                            if rfunc.logging:
                                Logger.info(
                                    f"{identify_str} -> [Bot]: {msg.trigger_msg}")
                            Logger.debug("Matched hash:" + str(matched_hash))
                            if msg.session_info.target_id not in match_hash_cache:
                                match_hash_cache[msg.session_info.target_id] = {}
                            if rfunc.logging and matched_hash in match_hash_cache[msg.session_info.target_id] and \
                                    datetime.now().timestamp() - match_hash_cache[msg.session_info.target_id][
                                    matched_hash] < int(
                                    (msg.session_info.target_info.target_data.get("cooldown_time", 0)) or 3):
                                Logger.warning("Match loop detected, skipping...")
                                continue
                            match_hash_cache[msg.session_info.target_id][matched_hash] = datetime.now().timestamp()

                            if enable_tos and rfunc.show_typing:
                                await _check_temp_ban(msg)
                            if rfunc.show_typing:
                                await _check_target_cooldown(msg)
                            if rfunc.required_superuser:
                                if not msg.check_super_user():
                                    continue
                            elif rfunc.required_admin:
                                if not await msg.check_permission():
                                    continue

                            if not regex_module.base:
                                if enable_tos and rfunc.show_typing:
                                    await _tos_msg_counter(msg, msg.trigger_msg)
                                else:
                                    Logger.debug(
                                        "Tos is disabled, check the configuration if it is not work as expected.")

                            if not ExecutionLockList.check(msg):
                                ExecutionLockList.add(msg)
                            else:
                                return await msg.send_message(I18NContext("parser.command.running.prompt"))

                            if rfunc.show_typing and msg.session_info.sender_info.sender_data.get(
                                    "typing_prompt", True):
                                await msg.start_typing()
                                _typing = True
                                await rfunc.function(msg)  # 将msg传入下游模块

                            else:
                                await rfunc.function(msg)  # 将msg传入下游模块
                            ExecutionLockList.remove(msg)
                            raise FinishedException(msg.sent)  # if not using msg.finish
                    except FinishedException as e:
                        time_used = datetime.now() - time_start
                        if rfunc.logging:
                            Logger.success(
                                f"Successfully finished session from {identify_str}, returns: {str(e)}. "
                                f"Times take up: {time_used}")

                        Info.command_parsed += 1
                        if enable_analytics:
                            await AnalyticsData.create(target_id=msg.session_info.target_id,
                                                       sender_id=msg.session_info.sender_id,
                                                       command=msg.trigger_msg,
                                                       module_name=m,
                                                       module_type="regex")
                        continue

                    except NoReportException as e:
                        await _process_noreport_exception(msg, e)

                    except AbuseWarning as e:
                        await _process_tos_abuse_warning(msg, e)

                    except Exception as e:
                        await _process_exception(msg, e)
                    finally:
                        if _typing:
                            await msg.end_typing()
                            ExecutionLockList.remove(msg)

        except SendMessageFailed:
            await _process_send_message_failed(msg)
            continue


async def _check_target_cooldown(msg: "Bot.MessageSession"):
    cooldown_time = int(msg.session_info.target_info.target_data.get("cooldown_time", 0))

    if cooldown_time and not await msg.check_permission():
        if sender_cooldown := cooldown_counter.setdefault(msg.session_info.target_id, {}).get(
                msg.session_info.sender_id):
            elapsed = datetime.now().timestamp() - sender_cooldown["ts"]
            if elapsed <= cooldown_time:
                if not sender_cooldown.get("notified", False):
                    sender_cooldown["notified"] = True
                    await msg.finish(I18NContext("message.cooldown.manual", time=int(cooldown_time - elapsed)))
                await msg.finish()
            sender_cooldown.update({"ts": datetime.now().timestamp(), "notified": False})
        else:
            cooldown_counter[msg.session_info.target_id] = {
                msg.session_info.sender_id: {"ts": datetime.now().timestamp(), "notified": False}}


async def _check_temp_ban(msg: "Bot.MessageSession"):
    is_temp_banned = temp_ban_counter.get(msg.session_info.sender_id)
    if is_temp_banned:
        if msg.check_super_user():
            await remove_temp_ban(msg.session_info.sender_id)
            return None
        ban_time = datetime.now().timestamp() - is_temp_banned["ts"]
        if ban_time < TOS_TEMPBAN_TIME:
            if is_temp_banned["count"] < 2:
                is_temp_banned["count"] += 1
                await msg.finish(I18NContext("tos.message.tempbanned", ban_time=int(TOS_TEMPBAN_TIME - ban_time)))
            elif is_temp_banned["count"] <= 3:
                is_temp_banned["count"] += 1
                await msg.finish(
                    I18NContext("tos.message.tempbanned.warning", ban_time=int(TOS_TEMPBAN_TIME - ban_time)))
            else:
                raise AbuseWarning("{I18N:tos.message.reason.ignore}")


async def _tos_msg_counter(msg: "Bot.MessageSession", command: str):
    same = counter_same.get(msg.session_info.sender_id)
    if not same or datetime.now().timestamp() - same["ts"] > 300 or same["command"] != command:
        # 检查是否滥用（5分钟内重复使用同一命令10条）

        counter_same[msg.session_info.sender_id] = {"command": command, "count": 1,
                                                    "ts": datetime.now().timestamp()}
    else:
        same["count"] += 1
        if same["count"] > 10:
            raise AbuseWarning("{I18N:tos.message.reason.cooldown}")
    all_ = counter_all.get(msg.session_info.sender_id)
    if not all_ or datetime.now().timestamp() - all_["ts"] > 300:  # 检查是否滥用（5分钟内使用20条命令）
        counter_all[msg.session_info.sender_id] = {"count": 1,
                                                   "ts": datetime.now().timestamp()}
    else:
        all_["count"] += 1
        if all_["count"] > 20:
            raise AbuseWarning("{I18N:tos.message.reason.abuse}")


async def _execute_module_command(msg: "Bot.MessageSession", module, command_first_word):
    bot: "Bot" = exports["Bot"]
    try:
        command_parser = CommandParser(module, msg=msg, module_name=command_first_word,
                                       command_prefixes=msg.session_info.prefixes)
        try:
            parsed_msg = command_parser.parse(msg.trigger_msg)  # 解析模块的子功能命令
            command: CommandMeta = parsed_msg[0]
            msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
            Logger.trace("Parsed message: " + str(msg.parsed_msg))

            if command.required_base_superuser:
                if msg.session_info.sender_id not in bot.base_superuser_list:
                    await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                    return
            elif command.required_superuser:
                if not msg.check_super_user():
                    await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                    return
            elif command.required_admin:
                if not await msg.check_permission():
                    await msg.send_message(I18NContext("parser.admin.command.permission.denied"))
                    return

            if not command.load or \
                msg.session_info.target_from in command.exclude_from or \
                msg.session_info.client_name in command.exclude_from or \
                ("*" not in command.available_for and
                 msg.session_info.target_from not in command.available_for and
                 msg.session_info.client_name not in command.available_for):
                raise InvalidCommandFormatError

            kwargs = {}
            func_params = inspect.signature(command.function).parameters
            if len(func_params) > 1 and msg.parsed_msg:
                parsed_msg_ = msg.parsed_msg.copy()
                no_message_session = True
                for param_name, param_obj in func_params.items():
                    if param_obj.annotation == bot.MessageSession:
                        kwargs[param_name] = msg
                        no_message_session = False
                    elif isinstance(param_obj.annotation, Param):
                        if param_obj.annotation.name in parsed_msg_:
                            if isinstance(
                                    parsed_msg_[
                                        param_obj.annotation.name],
                                    param_obj.annotation.type):
                                kwargs[param_name] = parsed_msg_[param_obj.annotation.name]
                                del parsed_msg_[param_obj.annotation.name]
                            else:
                                Logger.warning(f"{param_obj.annotation.name} is not a {
                                    param_obj.annotation.type}")
                        else:
                            Logger.warning(f"{param_obj.annotation.name} is not in parsed_msg")
                    param_name_ = param_name

                    if (param_name__ := f"<{param_name}>") in parsed_msg_:
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
                if no_message_session:
                    Logger.warning(
                        f"{command.function.__name__} has no Bot.MessageSession parameter, did you forgot to add it?\n"
                        "Remember: MessageSession IS NOT Bot.MessageSession")
            else:
                kwargs[func_params[list(func_params.keys())[0]].name] = msg

            if msg.session_info.target_info.target_data.get("typing_prompt", True):
                await msg.start_typing()
            await parsed_msg[0].function(**kwargs)  # 将msg传入下游模块

            raise FinishedException(msg.sent)  # if not using msg.finish
        except InvalidCommandFormatError:
            if not msg.session_info.sender_info.sender_data.get("typo_check", True):
                await msg.send_message(I18NContext("parser.command.invalid.format",
                                                   module=command_first_word,
                                                   prefix=msg.session_info.prefixes[0]))
            return
        except Exception as e:
            raise e
    except InvalidHelpDocTypeError:
        Logger.exception()
        await msg.send_message(I18NContext("error.module.helpdoc_invalid", module=command_first_word))
        return


async def _process_tos_abuse_warning(msg: "Bot.MessageSession", e: AbuseWarning):
    if enable_tos and Config("tos_warning_counts", 5) >= 1 and not msg.check_super_user():
        await abuse_warn_target(msg, str(e))
        temp_ban_counter[msg.session_info.sender_id] = {"count": 1,
                                                        "ts": datetime.now().timestamp()}
    else:
        err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
        err_msg_chain.append(Plain(msg.session_info.locale.t_str(str(e))))
        err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
        await msg.send_message(err_msg_chain)


async def _process_send_message_failed(msg: "Bot.MessageSession"):
    await msg.handle_error_signal()
    await msg.send_message(I18NContext("error.message.limited"))


async def _process_noreport_exception(msg: "Bot.MessageSession", e: NoReportException):
    Logger.exception()
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg = msg.session_info.locale.t_str(str(e))
    err_msg_chain += match_kecode(err_msg)
    err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)


async def _process_exception(msg: "Bot.MessageSession", e: Exception):
    bot: "Bot" = exports["Bot"]
    tb = traceback.format_exc()
    Logger.error(tb)
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg = msg.session_info.locale.t_str(str(e))
    err_msg_chain += match_kecode(err_msg)
    await msg.handle_error_signal()

    external = False
    if "timeout" in err_msg.lower().replace(" ", ""):
        external = True
    else:
        try:
            status_code = int(str(e).strip().split("[")[0])
            expected_msg = f"{status_code}[KE:Image,path=https://http.cat/{status_code}.jpg]"
            if err_msg == expected_msg and 500 <= status_code < 600:
                external = True
        except Exception:
            pass

    if external:
        err_msg_chain.append(I18NContext("error.message.prompt.external"))
    else:
        err_msg_chain.append(I18NContext("error.message.prompt.report"))

    if bug_report_url:
        err_msg_chain.append(I18NContext("error.message.prompt.address", url=bug_report_url))
    await msg.send_message(err_msg_chain)

    if not external and report_targets:
        for target in report_targets:
            if f := await bot.fetch_target(target):
                await bot.send_direct_message(f, [I18NContext("error.message.report", command=msg.trigger_msg),
                                                  Plain(tb.strip(), disable_joke=True)],
                                              enable_parse_message=False, disable_secret_check=True)


async def _command_typo_check(msg: "Bot.MessageSession", modules, command_first_word):
    bot: "Bot" = exports["Bot"]
    is_base_superuser = msg.session_info.sender_id in bot.base_superuser_list
    is_superuser = msg.check_super_user()

    available_modules = []
    for x in modules:
        if modules[x].base or (x in msg.session_info.enabled_modules):
            if modules[x].hidden:
                continue
            if modules[x].required_superuser and not is_superuser:
                continue
            if modules[x].required_base_superuser and not is_base_superuser:
                continue
            available_modules.append(x)

    match_close_module: list = difflib.get_close_matches(
        command_first_word, available_modules, 1, typo_check_module_score)
    if match_close_module:
        Logger.debug(f"Match module: {command_first_word} -> {match_close_module[0]}")
        module: Module = modules[match_close_module[0]]

        none_template = True  # 检查模块绑定的命令是否有文档
        for func in module.command_list.get(msg.session_info.target_from):
            if func.command_template:
                none_template = False

        command_split = msg.trigger_msg.split(" ")
        len_command_split = len(command_split)
        if not none_template and len_command_split > 1:
            get_commands: List[CommandMeta] = module.command_list.get(msg.session_info.target_from)
            command_templates = {}  # 根据命令模板的空格数排序命令
            for func in get_commands:
                command_template: List[argsTemplate] = copy.deepcopy(func.command_template)
                for ct in command_template:
                    ct.args_ = [a for a in ct.args if isinstance(a, ArgumentPattern)]
                    if (len_args := len(ct.args)) not in command_templates:
                        command_templates[len_args] = [ct]
                    else:
                        command_templates[len_args].append(ct)

            if len_command_split - 1 > len(command_templates):  # 如果空格数远大于命令模板的空格数
                select_templates = command_templates[max(command_templates)]
            else:
                try:
                    select_templates = command_templates[len_command_split - 1]  # 选择匹配的命令组
                except KeyError:
                    # 找一个最接近的命令模板
                    select_templates = command_templates[max(
                        command_templates.keys(), key=lambda k: min(abs(k - (len_command_split - 1)), k))]
            match_close_command: list = difflib.get_close_matches(
                " ".join(command_split[1:]), templates_to_str(select_templates), 1, typo_check_command_score)  # 进一步匹配命令
            if match_close_command:
                Logger.debug(f"Match command: {" ".join(command_split[1:])} -> {match_close_command[0]}")
                match_split = match_close_command[0]
                m_split_options = filter(None, re.split(r"(\[.*?\])", match_split))  # 切割可选参数
                old_command_split = command_split.copy()
                del old_command_split[0]
                new_command_split = [match_close_module[0]]
                for m_ in m_split_options:
                    if m_.startswith("["):  # 如果是可选参数
                        m_split = m_.split(" ")  # 切割可选参数中的空格（说明存在多个子必须参数）
                        if len(m_split) > 1:
                            match_close_options = difflib.get_close_matches(
                                m_split[0][1:], old_command_split, 1, typo_check_options_score)  # 进一步匹配可选参数
                            if match_close_options:
                                Logger.debug(f"Match close options: {m_split[0][1:]} -> {match_close_options[0]}")
                                position = old_command_split.index(match_close_options[0])  # 定位可选参数的位置
                                new_command_split.append(m_split[0][1:])  # 将可选参数插入到新命令列表中
                                new_command_split += old_command_split[position + 1: position + len(m_split)]
                                del old_command_split[position: position + len(m_split)]  # 删除原命令列表中的可选参数
                        else:
                            if m_split[0][1] == "<":
                                new_command_split.append(old_command_split[0])
                                del old_command_split[0]
                            else:
                                new_command_split.append(m_split[0][1:-1])
                    else:
                        m__ = filter(None, m_.split(" "))  # 必须参数
                        for mm in m__:
                            if len(old_command_split) > 0:
                                if mm.startswith("<"):
                                    new_command_split.append(old_command_split[0])
                                    del old_command_split[0]
                                else:
                                    match_close_args = difflib.get_close_matches(
                                        old_command_split[0], [mm], 1, typo_check_args_score)  # 进一步匹配参数
                                    if match_close_args:
                                        Logger.debug(f"Match close args: {
                                                     old_command_split[0]} -> {match_close_args[0]}")
                                        new_command_split.append(mm)
                                        del old_command_split[0]
                                    else:
                                        new_command_split.append(old_command_split[0])
                                        del old_command_split[0]
                            else:
                                new_command_split.append(mm)
                new_command_display = " ".join(new_command_split)
                if new_command_display != msg.trigger_msg:
                    wait_confirm = await msg.wait_confirm(I18NContext("parser.command.fixup.confirm", command=f"{msg.session_info.prefixes[0]}{new_command_display}"))
                    if wait_confirm:
                        command_first_word = new_command_split[0]
                        msg.trigger_msg = " ".join(new_command_split)
                        return msg, command_first_word, True
                    return None, None, True
            else:
                if len_command_split - 1 == 1:
                    new_command_display = f"{match_close_module[0]} {" ".join(command_split[1:])}"
                    if new_command_display != msg.trigger_msg:
                        wait_confirm = await msg.wait_confirm(
                            I18NContext("parser.command.fixup.confirm", command=f"{msg.session_info.prefixes[0]}{new_command_display}"))
                        if wait_confirm:
                            command_first_word = match_close_module[0]
                            msg.trigger_msg = " ".join([match_close_module[0]] + command_split[1:])
                            return msg, command_first_word, True
                        return None, None, True
        else:
            new_command_display = f"{
                match_close_module[0] + (" " + " ".join(command_split[1:]) if len(command_split) > 1 else "")}"
            if new_command_display != msg.trigger_msg:
                wait_confirm = await msg.wait_confirm(I18NContext("parser.command.fixup.confirm", command=f"{msg.session_info.prefixes[0]}{new_command_display}"))
                if wait_confirm:
                    command_first_word = match_close_module[0]
                    msg.trigger_msg = match_close_module[0]
                    return msg, command_first_word, True
                return None, None, True
    return None, None, False

__all__ = ["parser", "check_temp_ban", "remove_temp_ban"]
