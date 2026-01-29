import inspect
import re
from typing import TYPE_CHECKING

from core.builtins.message.internal import I18NContext
from core.builtins.parser.command import CommandParser
from core.builtins.session.tasks import SessionTaskManager
from core.constants.exceptions import InvalidCommandFormatError, SessionFinished
from core.exports import exports
from core.loader import ModulesManager
from core.logger import Logger
from core.types import Module, Param
from core.types.module.component_meta import CommandMeta
from core.utils.func import normalize_space

if TYPE_CHECKING:
    from core.builtins.bot import Bot


async def parser(msg: "Bot.MessageSession"):
    await msg.session_info.refresh_info()

    await SessionTaskManager.check(msg)
    modules = ModulesManager.return_modules_list()

    msg.trigger_msg = normalize_space(msg.as_display())
    if len(msg.trigger_msg) == 0:
        return

    disable_prefix, in_prefix_list = _get_prefixes(msg)

    if in_prefix_list or disable_prefix:
        command_first_word = await _process_command(msg, modules, disable_prefix, in_prefix_list)

        if command_first_word in modules:  # 检查触发命令是否在模块列表中
            await _execute_module(msg, modules, command_first_word)
            return msg
        # 如果使用了前缀但未命中任何模块命令，则视为不匹配（适用于单元测试）
        return None

    # 检查正则
    # 若任何正则命中则会在 _execute_regex 中调用对应函数并抛出 SessionFinished
    await _execute_regex(msg, modules)
    # 若未命中任何正则，视为不匹配（适用于单元测试）
    return None


def _get_prefixes(msg: "Bot.MessageSession"):
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
            return False, False
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
        max_alias = str(max(alias_list, key=len))
        real_name = ModulesManager.modules_aliases[max_alias]
        command_words = command.split(" ")
        command_words = real_name.split(" ") + command_words[len(max_alias.split(" ")):]
        command = " ".join(command_words)

    msg.trigger_msg = command
    return command.split(" ")[0]


async def _execute_module(msg: "Bot.MessageSession", modules, command_first_word):
    module: Module = modules[command_first_word]
    if not module.command_list.set:  # 如果没有可用的命令，则展示模块简介
        if module.rss and not msg.session_info.support_rss:
            return
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

    none_templates = True  # 检查模块绑定的命令是否有模板
    for func in module.command_list.get(msg.session_info.target_from):
        if func.command_template:
            none_templates = False
    if not none_templates:  # 如果有，送入命令解析
        executed = await _execute_module_command(msg, module, command_first_word)
        if executed:
            raise SessionFinished  # if not using msg.finish
    # 如果没有，直接传入下游模块
    msg.parsed_msg = None
    for func in module.command_list.set:
        if not func.command_template:
            if hasattr(msg, "_casetest_target") and func.function is not msg._casetest_target:
                continue
            if msg.session_info.sender_info.sender_data.get("typing_prompt", True):
                await msg.start_typing()
            await func.function(msg)  # 将msg传入下游模块
            raise SessionFinished  # if not using msg.finish


async def _execute_regex(msg: "Bot.MessageSession", modules):
    for m in modules:  # 遍历模块
        if modules[m].regex_list.set:
            regex_module: Module = modules[m]

            for rfunc in regex_module.regex_list.set:  # 遍历正则模块的表达式
                matched = False
                trigger_msg = msg.as_display(text_only=rfunc.text_only, element_filter=rfunc.element_filter)
                if rfunc.mode.upper() in ["M", "MATCH"]:
                    msg.matched_msg = re.match(rfunc.pattern, trigger_msg, flags=rfunc.flags)
                    if msg.matched_msg:
                        matched = True
                elif rfunc.mode.upper() in ["A", "FINDALL"]:
                    msg.matched_msg = tuple(set(re.findall(rfunc.pattern, trigger_msg, flags=rfunc.flags)))
                    if msg.matched_msg:
                        matched = True

                if matched:  # 如果匹配成功
                    if hasattr(msg, "_casetest_target") and rfunc.function is not msg._casetest_target:
                        continue
                    await rfunc.function(msg)  # 将msg传入下游模块
                    raise SessionFinished  # if not using msg.finish


async def _execute_module_command(msg: "Bot.MessageSession", module, command_first_word):
    bot: "Bot" = exports["Bot"]
    command_parser = CommandParser(module, msg=msg, module_name=command_first_word,
                                   command_prefixes=msg.session_info.prefixes)
    parsed_msg = command_parser.parse(msg.trigger_msg)  # 解析模块的子功能命令
    command: CommandMeta = parsed_msg[0]
    msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
    Logger.trace("Parsed message: " + str(msg.parsed_msg))

    if hasattr(msg, "_casetest_target") and command.function is not msg._casetest_target:
        return False

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

    await parsed_msg[0].function(**kwargs)  # 将msg传入下游模块
    return True

__all__ = ["parser"]
