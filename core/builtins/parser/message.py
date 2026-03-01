"""
消息解析模块 - 处理消息的完整解析流程。

该模块是消息处理的核心，负责：
1. 接收消息会话
2. 检测和匹配命令模式
3. 解析命令参数
4. 执行相应的模块处理
5. 错误处理和用户反馈

包含了复杂的权限检查、速率限制、错误报告等功能。
"""

import copy
import difflib
import inspect
import re
import time
import traceback
from string import Template as stringTemplate
from typing import TYPE_CHECKING

from core.builtins.message.chain import MessageChain, match_kecode
from core.builtins.message.internal import Plain, I18NContext
from core.builtins.parser.args import ArgumentPattern, Template as argsTemplate, templates_to_str
from core.builtins.parser.command import CommandParser
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.config import Config
from core.constants.default import bug_report_url_default, ignored_sender_default
from core.constants.exceptions import (
    AbuseWarning,
    ExternalException,
    InvalidCommandFormatError,
    InvalidHelpDocTypeError,
    NoReportException,
    SessionFinished,
    SendMessageFailed,
    WaitCancelException,
)
from core.constants.info import Info
from core.database.models import AnalyticsData
from core.exports import exports
from core.loader import ModulesManager
from core.logger import Logger
from core.tos import TOS_TEMPBAN_TIME, temp_ban_counter, abuse_warn_target, remove_temp_ban
from core.types import Module, Param
from core.types.module.component_meta import CommandMeta
from core.utils.func import normalize_space
from core.utils.container import ExpiringTempDict, TokenBucket

if TYPE_CHECKING:
    from core.builtins.bot import Bot

# ========== 全局配置项 ==========

# 忽略的发送者列表 - 这些用户的消息不会被处理
ignored_sender = Config("ignored_sender", ignored_sender_default)

# ========== 功能开关 ==========

# 是否启用服务条款检查（检查用户是否同意 ToS）
enable_tos = Config("enable_tos", True)

# 是否启用分析统计（记录命令执行情况）
enable_analytics = Config("enable_analytics", True)

# 错误报告的目标列表（将错误信息发送给这些用户）
report_targets = Config("report_targets", [])

# 是否启用模块无效提示（用户输入错误的模块名时是否提示）
enable_module_invalid_prompt = Config("enable_module_invalid_prompt", False)

# Bug 报告的 URL
bug_report_url = Config("bug_report_url", bug_report_url_default)

# ========== 错字检查的分数阈值 ==========
# 这些阈值用于模糊匹配（当用户输入可能有错字时）

# 模块名的相似度阈值
typo_check_module_score = Config("typo_check_module_score", 0.6)

# 命令名的相似度阈值
typo_check_command_score = Config("typo_check_command_score", 0.3)

# 参数的相似度阈值
typo_check_args_score = Config("typo_check_args_score", 0.5)

# 选项的相似度阈值
typo_check_options_score = Config("typo_check_options_score", 0.3)

# ========== 频率限制相关 ==========

# 命令使用次数计数（重复使用单一命令）
# 用于检测用户是否过度使用同一命令
buckets_same = ExpiringTempDict()

# 命令使用次数计数（使用所有命令）
# 用于检测用户是否过度使用命令（整体频率）
buckets_all = ExpiringTempDict()

# 冷却计数 - 记录被暂时禁止的用户和禁止时长
target_cooldown_counter = ExpiringTempDict(exp=TOS_TEMPBAN_TIME)

# 匹配哈希缓存 - 缓存消息与模块的匹配结果，加速处理
match_hash_cache = ExpiringTempDict()


async def parser(msg: "Bot.MessageSession"):
    """
    消息处理的主入口函数。

    这是所有消息必经的预处理器，负责：
    1. 消息格式化和验证
    2. 权限检查
    3. 命令匹配和执行
    4. 正则表达式匹配
    5. 错误处理和用户反馈

    工作流程：
    1. 刷新用户和目标信息（从数据库）
    2. 检查黑名单和权限
    3. 提取消息前缀，判断是否为命令
    4. 若是命令，进行命令解析和执行
    5. 若不是命令，进行正则表达式匹配
    6. 处理所有异常和错误情况

    :param msg: 从监听器接收到的 MessageSession，该会话将通过此预处理器传入下游模块
    """
    # 刷新会话信息（从数据库重新加载最新数据）
    await msg.session_info.refresh_info()

    # 创建标识字符串用于日志记录
    identify_str = f"[{msg.session_info.sender_id} ({msg.session_info.target_id})]"

    # 检查发送者是否在忽略列表中
    if msg.session_info.sender_id in ignored_sender:
        return

    try:
        # ========== 步骤 1: 检查任务队列 ==========
        # 检查是否有等待此消息的任务（如等待用户回复）
        await SessionTaskManager.check(msg)

        # 获取该平台和客户端的所有可用模块
        modules = ModulesManager.return_modules_list(msg.session_info.target_from, msg.session_info.client_name)

        # 将消息转换为易读的显示格式
        msg.trigger_msg = normalize_space(msg.as_display())

        # 如果消息为空，直接返回
        if len(msg.trigger_msg) == 0:
            return

        # ========== 步骤 2: 权限检查 ==========
        # 检查发送者是否被被机器人屏蔽（机器人黑名单）
        if msg.session_info.sender_info.blocked and not (
            msg.session_info.sender_info.trusted or msg.session_info.sender_info.superuser
        ):
            return

        # 检查发送者是否在会话的屏蔽用户列表中（会话黑名单）
        if msg.session_info.sender_id in msg.session_info.banned_users and not msg.session_info.superuser:
            return

        # ========== 步骤 3: 命令匹配 ==========
        # 检查消息是否以命令前缀开头
        disable_prefix, in_prefix_list = _get_prefixes(msg)

        if in_prefix_list or disable_prefix:  # 检查消息前缀
            Logger.info(f"{identify_str} -> [Bot]: {msg.trigger_msg}")
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
                if modules[command_first_word]._db_load:  # 检查模块是否已加载
                    await _execute_module(msg, modules, command_first_word, identify_str)
                else:
                    await msg.send_message(I18NContext("parser.module.unloaded", module=command_first_word))
            elif msg.session_info.sender_info.sender_data.get("typo_check", True):
                new_msg, new_command_first_word, confirmed = await _command_typo_check(msg, modules, command_first_word)
                if new_msg:
                    if modules[new_command_first_word]._db_load:  # 检查模块是否已加载
                        await _execute_module(new_msg, modules, new_command_first_word, identify_str)
                    else:
                        await msg.send_message(I18NContext("parser.module.unloaded", module=new_command_first_word))
                elif enable_module_invalid_prompt and not confirmed:
                    await msg.send_message(
                        I18NContext("parser.command.invalid.module", prefix=msg.session_info.prefixes[0])
                    )
            elif enable_module_invalid_prompt:
                await msg.send_message(
                    I18NContext("parser.command.invalid.module", prefix=msg.session_info.prefixes[0])
                )

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
        ExecutionLockList.remove(msg)
        Info.message_parsed += 1


def _transform_alias(msg, command: str):
    """
    转换自定义命令别名为实际命令。

    该函数处理用户自定义的命令别名，支持两种类型：
    1. 带占位符的别名（如 "aaa ${keyword}" -> "bbb ${keyword}"）
    2. 简单的文本替换别名（如 "enable" -> "module enable"）

    对于带占位符的别名，会优先选择占位符数量最多的匹配（复杂度最高优先）。

    :param msg: 消息会话对象
    :param command: 原始命令字符串
    :return: 转换后的命令字符串（如果没有匹配的别名，返回原命令）
    """
    # 从目标信息中获取自定义别名字典
    aliases = dict(msg.session_info.target_info.target_data.get("command_alias", {}).items())

    # 存储所有匹配的别名模板，格式: (占位符数量, 模式, 替换, 占位符列表, 匹配对象)
    matched_aliases = []

    # ========== 处理带占位符的别名 ==========
    for pattern, replacement in aliases.items():
        # 检查模式中是否包含占位符（格式: ${name}）
        if re.search(r"\${[^}]*}", pattern):
            # 处理连在一起的多个占位符，在它们之间插入空格
            # 例如: "${a}${b}" -> "${a} ${b}"
            normalized_pattern = re.sub(r"(\$\{\w+})(?=\$\{\w+})", r"\1 ", pattern)

            # 提取所有占位符的名称
            # 例如: "${keyword} ${type}" -> ["keyword", "type"]
            placeholders = re.findall(r"\$\{([^{}$]+)}", normalized_pattern)

            # 构造用于匹配的正则表达式
            # 将占位符替换为捕获组 (\S+)，用于匹配非空白字符
            regex_pattern = re.escape(normalized_pattern)
            for ph in placeholders:
                regex_pattern = regex_pattern.replace(re.escape(f"${{{ph}}}"), r"(\S+)")

            # 尝试匹配命令
            match = re.match(regex_pattern, command)
            if match:
                # 记录匹配结果：(占位符数量, 原始模式, 替换文本, 占位符列表, 匹配对象)
                matched_aliases.append((len(placeholders), pattern, replacement, placeholders, match))

    # ========== 选择最佳匹配 ==========
    # 如果有多个匹配，按占位符数量降序排列（复杂度高的优先）
    if matched_aliases:
        matched_aliases.sort(key=lambda x: x[0], reverse=True)

        # 使用复杂度最高的匹配
        _, pattern, replacement, placeholders, match = matched_aliases[0]
        groups = match.groups()

        # 创建占位符到实际值的映射字典
        placeholder_dict = {placeholders[i]: groups[i] for i in range(len(groups))}

        # 使用字符串模板替换占位符
        result = stringTemplate(replacement).safe_substitute(placeholder_dict)
        Logger.debug(msg.session_info.prefixes[0] + result)
        return msg.session_info.prefixes[0] + result

    # ========== 处理不带占位符的简单别名 ==========
    # 例如: "h" -> "help"
    for pattern, replacement in aliases.items():
        if not re.search(r"\${[^}]*}", pattern):
            # 如果命令以该模式开头，进行替换
            if command.startswith(pattern):
                new_command = command.replace(pattern, msg.session_info.prefixes[0] + replacement, 1)
                Logger.debug(new_command)
                return new_command

    # 没有匹配的别名，返回原命令
    return command


def _get_prefixes(msg: "Bot.MessageSession"):
    """
    检查并处理消息的命令前缀。

    该函数执行以下操作：
    1. 如果配置了自定义别名，先进行别名转换
    2. 检查是否禁用前缀（空字符串前缀）
    3. 检查消息是否以配置的前缀开头
    4. 如果匹配到前缀，将其移至前缀列表的首位（便于后续操作）

    :param msg: 消息会话对象
    :return: (disable_prefix, in_prefix_list) 元组
             - disable_prefix: 是否禁用前缀检查（True 表示任何消息都视为命令）
             - in_prefix_list: 消息是否以某个前缀开头
    """
    # ========== 步骤 1: 处理自定义别名 ==========
    if msg.session_info.target_info.target_data.get("command_alias"):
        # 将自定义别名替换为实际命令
        msg.trigger_msg = _transform_alias(msg, msg.trigger_msg)

    # ========== 步骤 2: 检查前缀配置 ==========
    disable_prefix = False
    # 如果上游指定了命令前缀，使用指定的命令前缀
    if msg.session_info.prefixes:
        # 如果前缀列表中包含空字符串，表示禁用前缀检查
        if "" in msg.session_info.prefixes:
            disable_prefix = True

    display_prefix = ""
    in_prefix_list = False

    # ========== 步骤 3: 检查消息是否以前缀开头 ==========
    for cp in msg.session_info.prefixes:
        if msg.trigger_msg.startswith(cp):
            display_prefix = cp
            in_prefix_list = True
            break

    # ========== 步骤 4: 前缀验证和优化 ==========
    if in_prefix_list or disable_prefix:
        # 排除特殊情况：消息太短或是删除线格式（~~xxx~~）
        if len(msg.trigger_msg) <= 1 or msg.trigger_msg[:2] == "~~":
            return False, False

        # 如果匹配到前缀，将其移到列表首位
        if in_prefix_list:
            msg.session_info.prefixes.remove(display_prefix)
            msg.session_info.prefixes.insert(0, display_prefix)

    return disable_prefix, in_prefix_list


async def _process_command(msg: "Bot.MessageSession", modules, disable_prefix, in_prefix_list):
    """
    处理和解析命令字符串。

    该函数负责：
    1. 移除命令前缀，提取实际命令
    2. 检查命令是否为模块的直接名称
    3. 处理命令别名（多词别名）
    4. 将别名转换为实际的模块命令

    别名处理逻辑：
    - 支持多词别名（如 "aaa bbb" 作为某个命令的别名）
    - 优先匹配最长的别名（避免误匹配）
    - 如果命令已经是实际模块名，只匹配该模块下的别名

    :param msg: 消息会话对象
    :param modules: 可用的模块字典
    :param disable_prefix: 是否禁用前缀
    :param in_prefix_list: 消息是否以前缀开头
    :return: 命令的第一个词（模块名）
    """
    # ========== 步骤 1: 移除命令前缀 ==========
    if disable_prefix and not in_prefix_list:
        # 禁用前缀模式，使用完整消息作为命令
        command = msg.trigger_msg
    else:
        # 移除前缀，提取实际命令
        command = msg.trigger_msg[len(msg.session_info.prefixes[0]) :]

    command = command.strip()
    command_split: list = command.split(" ")  # 切割消息为单词列表

    # ========== 步骤 2: 检查是否为实际模块名 ==========
    not_alias = False
    cm = ""
    for module_name in modules:
        if command_split[0] == module_name:
            # 找到了匹配的模块，标记为非别名
            not_alias = True
            cm = module_name
            break

    # ========== 步骤 3: 收集可能匹配的别名 ==========
    alias_list = []
    for alias, _ in ModulesManager.modules_aliases.items():
        alias_words = alias.split(" ")
        cmd_words = command.split(" ")

        if not not_alias:
            # 如果第一个词不是模块名，检查所有别名
            if cmd_words[: len(alias_words)] == alias_words:
                alias_list.append(alias)
        else:
            # 如果第一个词是模块名，只检查该模块下的别名
            if alias.startswith(cm):
                if cmd_words[: len(alias_words)] == alias_words:
                    alias_list.append(alias)

    # ========== 步骤 4: 应用最长匹配的别名 ==========
    if alias_list:
        # 选择最长的别名（避免短别名误匹配）
        max_alias = str(max(alias_list, key=len))
        # 获取别名对应的实际模块名
        real_name = ModulesManager.modules_aliases[max_alias]

        # 重构命令：实际模块名 + 别名后的剩余参数
        command_words = command.split(" ")
        command_words = real_name.split(" ") + command_words[len(max_alias.split(" ")) :]
        command = " ".join(command_words)

    # 更新消息的触发命令
    msg.trigger_msg = command

    # 返回命令的第一个词（模块名）
    return command.split(" ")[0]


async def _execute_module(msg: "Bot.MessageSession", modules, command_first_word, identify_str):
    """
    执行模块的命令处理逻辑。

    这是命令执行的核心函数，负责：
    1. 权限检查（超级用户、管理员、模块启用状态等）
    2. 服务条款（ToS）检查和滥用检测
    3. 命令模板解析或直接传递消息
    4. 错误处理和异常报告
    5. 分析数据记录

    权限层级（从高到低）：
    - required_base_superuser: 基础超级用户（最高权限）
    - required_superuser: 超级用户
    - required_admin: 管理员
    - 普通用户

    :param msg: 消息会话对象
    :param modules: 可用的模块字典
    :param command_first_word: 命令的第一个词（模块名）
    :param identify_str: 用于日志的标识字符串
    """
    time_start = time.perf_counter()
    bot: "Bot" = exports["Bot"]
    _typing = False  # 标记是否正在显示“正在输入……”状态
    try:
        # ========== 步骤 1: 冷却检查 ==========
        # 检查目标是否在冷却期内（被临时禁止）
        await _check_target_cooldown(msg)

        # ========== 步骤 2: ToS 临时封禁检查 ==========
        if enable_tos:
            await _tos_temp_ban(msg)

        # ========== 步骤 3: 获取模块并检查是否有可用命令 ==========
        module: Module = modules[command_first_word]
        if not module.command_list.set:
            # 模块没有可用的命令，展示模块简介
            if module.rss and not msg.session_info.support_rss:
                # RSS 模块但平台不支持，直接返回
                return
            if module.desc:
                # 发送模块描述
                desc = [I18NContext("parser.module.desc", desc=msg.session_info.locale.t_str(module.desc))]
                if command_first_word not in msg.session_info.enabled_modules:
                    # 模块未启用，添加提示
                    desc.append(
                        I18NContext(
                            "parser.module.disabled.prompt",
                            module=command_first_word,
                            prefix=msg.session_info.prefixes[0],
                        )
                    )
                await msg.send_message(desc)
            else:
                # 没有描述，报告未绑定
                await msg.send_message(I18NContext("error.module.unbound", module=command_first_word))
            return

        # ========== 步骤 4: 权限检查 ==========
        if module.required_base_superuser:
            # 需要基础超级用户权限
            if msg.session_info.sender_id not in bot.base_superuser_list:
                await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                return
        elif module.required_superuser:
            # 需要超级用户权限
            if not msg.check_super_user():
                await msg.send_message(I18NContext("parser.superuser.permission.denied"))
                return
        elif not module.base:
            # 普通模块，检查是否已启用
            if command_first_word not in msg.session_info.enabled_modules and msg.session_info.require_enable_modules:
                # 模块未启用
                if await msg.check_permission():
                    # 用户有权限，询问是否启用
                    await msg.send_message(
                        I18NContext(
                            "parser.module.disabled.prompt",
                            module=command_first_word,
                            prefix=msg.session_info.prefixes[0],
                        )
                    )
                    if await msg.wait_confirm(I18NContext("parser.module.disabled.to_enable"), no_confirm_action=False):
                        # 用户确认启用
                        await msg.session_info.target_info.config_module(command_first_word)
                        await msg.send_message(
                            I18NContext("core.message.module.enable.success", module=command_first_word)
                        )
                    else:
                        # 用户取消，终止执行
                        return
                else:
                    # 用户无权限，直接拒绝
                    await msg.finish(I18NContext("parser.module.disabled", module=command_first_word))
        elif module.required_admin:
            # 需要管理员权限
            if not await msg.check_permission():
                await msg.send_message(I18NContext("parser.admin.permission.denied.module", module=command_first_word))
                return

        # ========== 步骤 5: ToS 消息计数 ==========
        if not module.base:
            if enable_tos:
                # 记录消息使用情况（用于滥用检测）
                await _tos_msg_counter(msg, msg.trigger_msg)
            else:
                Logger.debug("Tos is disabled, check the configuration if it is not work as expected.")

        # ========== 步骤 6: 检查并处理命令模板 ==========
        none_templates = True  # 标记模块是否有命令模板
        for func in module.command_list.get(msg.session_info.target_from):
            if func.command_template:
                none_templates = False
                break

        if not none_templates:
            # 有命令模板，进行命令解析
            await _execute_module_command(msg, module, command_first_word)
            raise SessionFinished(msg.sent)  # 如果模块没有使用 msg.finish，手动结束会话

        # ========== 步骤 7: 无模板，直接传递消息 ==========
        # 模块没有命令模板，直接将消息传给模块处理
        msg.parsed_msg = None
        for func in module.command_list.set:
            if not func.command_template:
                # 显示“正在输入……”状态（如果用户启用）
                if msg.session_info.sender_info.sender_data.get("typing_prompt", True):
                    await msg.start_typing()
                    _typing = True
                # 执行模块函数
                await func.function(msg)
                raise SessionFinished(msg.sent)

        # ========== 步骤 8: 错字检查 ==========
        if msg.session_info.sender_info.sender_data.get("typo_check", True):
            # 用户启用了错字检查，尝试纠正命令
            new_msg, new_command_first_word, confirmed = await _command_typo_check(msg, modules, command_first_word)
            if new_msg:
                # 找到了可能的正确命令
                if modules[new_command_first_word]._db_load:  # 检查模块是否已加载
                    await _execute_module(new_msg, modules, new_command_first_word, identify_str)
                else:
                    await msg.send_message(I18NContext("parser.module.unloaded", module=new_command_first_word))
            elif not confirmed:
                # 没有找到匹配的命令，提示语法错误
                await msg.send_message(
                    I18NContext(
                        "parser.command.invalid.syntax", module=command_first_word, prefix=msg.session_info.prefixes[0]
                    )
                )
    except SendMessageFailed:
        await _process_send_message_failed(msg)

    # ========== 异常处理 ==========
    except SessionFinished as e:
        # 会话正常结束
        time_used = time.perf_counter() - time_start
        Logger.success(
            f"Successfully finished session from {identify_str}, returns: {str(e)}. Times take up: {time_used:06f}s"
        )
        # 增加命令解析计数器
        Info.command_parsed += 1

        # 记录分析数据
        if enable_analytics:
            await AnalyticsData.create(
                target_id=msg.session_info.target_id,
                sender_id=msg.session_info.sender_id,
                command=msg.trigger_msg,
                module_name=command_first_word,
                module_type="normal",
            )

    except ExternalException as e:
        # 外部异常（如网络错误、API 错误）
        await _process_external_exception(msg, e)

    except AbuseWarning as e:
        # ToS 滥用警告
        await _process_tos_abuse_warning(msg, e)

    except NoReportException as e:
        # 无需报告的异常（已知的用户错误）
        await _process_noreport_exception(msg, e)

    except Exception as e:
        # 其他未预期的异常
        if "timeout" in str(e).lower().replace(" ", ""):
            # 超时相关的异常作为外部异常处理
            await _process_external_exception(msg, e)
        else:
            # 其他异常，记录详细信息并报告
            await _process_exception(msg, e)
    finally:
        # 清理工作
        if _typing:
            # 结束“正在输入……”状态
            await msg.end_typing()
        # 释放执行锁
        ExecutionLockList.remove(msg)


async def _execute_regex(msg: "Bot.MessageSession", modules, identify_str):
    """
    执行正则表达式匹配的模块。

    该函数遍历所有已启用的模块，查找包含正则表达式匹配规则的模块，
    并尝试用正则表达式匹配消息内容。如果匹配成功，执行相应的模块函数。

    正则匹配流程：
    1. 遍历所有已加载的模块
    2. 检查模块是否已启用且有正则表达式列表
    3. 检查用户权限
    4. 检查模块的可用性和平台限制
    5. 尝试匹配正则表达式
    6. 执行匹配成功的模块函数

    :param msg: 消息会话对象
    :param modules: 可用的模块字典
    :param identify_str: 用于日志的标识字符串
    """
    bot: "Bot" = exports["Bot"]

    # ========== 遍历所有模块 ==========
    for m in modules:
        # 跳过未加载的模块
        if not modules[m]._db_load:
            continue

        try:
            # ========== 步骤 1: 检查模块是否已启用且有正则表达式 ==========
            if m in msg.session_info.enabled_modules and modules[m].regex_list.set:
                regex_module: Module = modules[m]

                # ========== 步骤 2: 权限检查 ==========
                if regex_module.required_base_superuser:
                    # 需要基础超级用户权限
                    if msg.session_info.sender_id not in bot.base_superuser_list:
                        continue
                elif regex_module.required_superuser:
                    # 需要超级用户权限
                    if not msg.check_super_user():
                        continue
                elif regex_module.required_admin:
                    # 需要管理员权限
                    if not await msg.check_permission():
                        continue

                # ========== 步骤 3: 检查模块可用性和平台限制 ==========
                if (
                    not regex_module.load  # 模块未加载
                    or msg.session_info.target_from in regex_module.exclude_from  # 平台被排除
                    or msg.session_info.client_name in regex_module.exclude_from  # 客户端被排除
                    or (
                        "*" not in regex_module.available_for  # 不是对所有平台可用
                        and msg.session_info.target_from not in regex_module.available_for  # 且当前平台不在列表中
                        and msg.session_info.client_name not in regex_module.available_for
                    )
                ):
                    continue

                # ========== 步骤 4: 遍历模块的所有正则表达式 ==========
                for rfunc in regex_module.regex_list.set:
                    time_start = time.perf_counter()
                    matched = False  # 标记是否匹配成功
                    _typing = False  # 标记是否显示“正在输入……”
                    try:
                        matched_hash = 0  # 用于检测重复匹配

                        # 获取要匹配的消息文本（可能只包含纯文本或过滤特定元素）
                        trigger_msg = msg.as_display(text_only=rfunc.text_only, element_filter=rfunc.element_filter)

                        # ========== 步骤 5: 执行正则表达式匹配 ==========
                        if rfunc.mode.upper() in ["M", "MATCH"]:
                            # 使用 re.match（从字符串开头匹配）
                            msg.matched_msg = re.match(rfunc.pattern, trigger_msg, flags=rfunc.flags)
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg.groups())
                        elif rfunc.mode.upper() in ["A", "FINDALL"]:
                            # 使用 re.findall（查找所有匹配）
                            msg.matched_msg = tuple(set(re.findall(rfunc.pattern, trigger_msg, flags=rfunc.flags)))
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg)

                        # ========== 步骤 6: 处理匹配成功的情况 ==========
                        if (
                            matched
                            and regex_module.load
                            and not (
                                msg.session_info.target_from in regex_module.exclude_from
                                or msg.session_info.client_name in regex_module.exclude_from
                                or (
                                    "*" not in regex_module.available_for
                                    and msg.session_info.target_from not in regex_module.available_for
                                    and msg.session_info.client_name not in regex_module.available_for
                                )
                            )
                        ):
                            # 记录日志
                            if rfunc.logging:
                                Logger.info(f"{identify_str} -> [Bot]: {msg.trigger_msg}")
                            Logger.debug("Matched hash:" + str(matched_hash))

                            # ========== 循环匹配检测 ==========
                            # 获取冷却时间设置
                            cooldown_time = int(msg.session_info.target_info.target_data.get("cooldown_time", 0) or 3)

                            # 检查是否重复匹配
                            if rfunc.logging and matched_hash in match_hash_cache[msg.session_info.target_id]:
                                Logger.warning("Match loop detected, skipping...")
                                continue

                            # 记录匹配哈希到缓存
                            match_hash_cache[msg.session_info.target_id][matched_hash] = ExpiringTempDict(
                                exp=cooldown_time, root=False
                            )

                            # ========== ToS 和冷却检查 ==========
                            if enable_tos and rfunc.show_typing:
                                await _tos_temp_ban(msg)
                            if rfunc.show_typing:
                                await _check_target_cooldown(msg)

                            # ========== 正则表达式级别的权限检查 ==========
                            if rfunc.required_superuser:
                                if not msg.check_super_user():
                                    continue
                            elif rfunc.required_admin:
                                if not await msg.check_permission():
                                    continue

                            # ========== ToS 消息计数 ==========
                            if not regex_module.base:
                                if enable_tos and rfunc.show_typing:
                                    await _tos_msg_counter(msg, msg.trigger_msg)
                                else:
                                    Logger.debug(
                                        "Tos is disabled, check the configuration if it is not work as expected."
                                    )

                            if not ExecutionLockList.check(msg):
                                ExecutionLockList.add(msg)
                            else:
                                return await msg.send_message(I18NContext("parser.command.running.prompt"))

                            if rfunc.show_typing and msg.session_info.sender_info.sender_data.get(
                                "typing_prompt", True
                            ):
                                await msg.start_typing()
                                _typing = True
                                await rfunc.function(msg)  # 将msg传入下游模块

                            else:
                                await rfunc.function(msg)  # 将msg传入下游模块
                            ExecutionLockList.remove(msg)
                            raise SessionFinished(msg.sent)  # if not using msg.finish
                    except SessionFinished as e:
                        time_used = time.perf_counter() - time_start
                        if rfunc.logging:
                            Logger.success(
                                f"Successfully finished session from {identify_str}, returns: {str(e)}. "
                                f"Times take up: {time_used:06f}s"
                            )

                        Info.command_parsed += 1
                        if enable_analytics:
                            await AnalyticsData.create(
                                target_id=msg.session_info.target_id,
                                sender_id=msg.session_info.sender_id,
                                command=msg.trigger_msg,
                                module_name=m,
                                module_type="regex",
                            )
                        continue

                    except ExternalException as e:
                        await _process_external_exception(msg, e)

                    except NoReportException as e:
                        await _process_noreport_exception(msg, e)

                    except AbuseWarning as e:
                        await _process_tos_abuse_warning(msg, e)

                    except Exception as e:
                        if "timeout" in str(e).lower().replace(" ", ""):
                            await _process_external_exception(msg, e)
                        else:
                            await _process_exception(msg, e)
                    finally:
                        if _typing:
                            await msg.end_typing()
                        ExecutionLockList.remove(msg)

        except SendMessageFailed:
            await _process_send_message_failed(msg)
            continue


async def _check_target_cooldown(msg: "Bot.MessageSession"):
    """
    检查目标是否在冷却期内。

    该函数实现了命令冷却机制，防止用户过于频繁地使用命令。
    冷却时间可在目标配置中设置，管理员和超级用户不受限制。

    工作流程：
    1. 获取冷却时间配置
    2. 检查用户是否有权限绕过冷却
    3. 检查用户是否在冷却期内
    4. 如果在冷却期，抛出异常阻止执行

    :param msg: 消息会话对象
    :raises NoReportException: 如果用户在冷却期内
    """
    # 获取目标配置的冷却时间（秒）
    cooldown_time = int(msg.session_info.target_info.target_data.get("cooldown_time", 0))

    # 如果没有配置冷却时间或用户有管理权限，直接返回
    if not cooldown_time or await msg.check_permission():
        return

    # 获取该目标的冷却记录
    target_record = target_cooldown_counter[msg.session_info.target_id]

    # 获取或创建该发送者的冷却记录
    sender_record = target_record.setdefault(
        msg.session_info.sender_id, ExpiringTempDict(exp=cooldown_time, root=False)
    )

    # 检查是否还在冷却期内
    if not sender_record.is_expired():
        # 如果还没有通知过用户，发送冷却提示
        if not sender_record.get("notified", False):
            sender_record["notified"] = True
            # 计算剩余冷却时间
            elapsed = cooldown_time - (time.time() - sender_record.ts)
            await msg.finish(I18NContext("message.cooldown.manual", time=int(elapsed)))
        await msg.finish()

    sender_record.refresh()
    sender_record["notified"] = False
    sender_record.exp = cooldown_time


async def _tos_temp_ban(msg: "Bot.MessageSession"):
    """
    检查用户是否被临时封禁（ToS 违规）。

    该函数实现了服务条款（Terms of Service）的临时封禁机制。
    当用户因滥用命令被临时封禁时，会阻止其执行命令并显示剩余封禁时间。
    超级用户可以自动解除封禁。

    封禁警告级别：
    - 第 1-2 次尝试：显示普通封禁消息
    - 第 3-4 次尝试：显示严重警告消息
    - 第 4 次以上：增加滥用警告次数

    :param msg: 消息会话对象
    :raises SessionFinished: 如果用户被封禁，终止会话
    """
    # 获取用户的封禁信息
    ban_info = temp_ban_counter.get(msg.session_info.sender_id)

    if ban_info and not ban_info.is_expired():
        # 用户在封禁期内

        # 超级用户可以自动解除封禁
        if msg.check_super_user():
            await remove_temp_ban(msg.session_info.sender_id)
            return None

        # 计算剩余封禁时间
        ban_time = time.time() - ban_info.ts
        remaining = int(TOS_TEMPBAN_TIME - ban_time)

        # 初始化尝试次数计数器
        if not ban_info.get("count", 0):
            ban_info["count"] = 0

        # 根据尝试次数显示不同级别的警告
        if ban_info["count"] < 2:
            # 前两次尝试：显示普通封禁消息
            ban_info["count"] += 1
            await msg.finish(I18NContext("tos.message.tempbanned", ban_time=remaining))
        elif ban_info["count"] <= 3:
            # 第 3-4 次尝试：显示严重警告
            ban_info["count"] += 1
            await msg.finish(I18NContext("tos.message.tempbanned.warning", ban_time=remaining))
        else:
            # 第 4 次以上尝试：抛出滥用警告
            raise AbuseWarning("{I18N:tos.message.reason.ignore}")


async def _tos_msg_counter(msg: "Bot.MessageSession", command: str):
    """
    ToS 消息计数器 - 检测命令使用频率防止滥用。

    该函数使用令牌桶算法限制用户的命令使用频率，分为两个层级：
    1. 单命令频率限制：同一命令 10 / 300秒
    2. 全局命令频率限制：所有命令 20 / 300秒

    当任一限制被触发时，抛出滥用警告。

    :param msg: 消息会话对象
    :param command: 命令字符串
    :raises AbuseWarning: 如果检测到滥用行为
    """
    # ========== 单命令频率检查 ==========
    # 检查同一命令的使用频率
    bucket_same = buckets_same[msg.session_info.sender_id][command]
    if "bucket" not in bucket_same:
        # 初始化令牌桶：容量 10，每 300 秒恢复满
        bucket_same["bucket"] = TokenBucket(10, 300)

    if not bucket_same["bucket"].consume():
        # 令牌耗尽，单命令使用过于频繁
        raise AbuseWarning("{I18N:tos.message.reason.cooldown}")

    # ========== 全局命令频率检查 ==========
    # 检查所有命令的总体使用频率
    bucket_all = buckets_all[msg.session_info.sender_id]
    if "bucket" not in bucket_all:
        # 初始化令牌桶：容量 20，每 300 秒恢复满
        bucket_all["bucket"] = TokenBucket(20, 300)

    if not bucket_all["bucket"].consume():
        # 令牌耗尽，整体命令使用过于频繁
        raise AbuseWarning("{I18N:tos.message.reason.abuse}")


async def _execute_module_command(msg: "Bot.MessageSession", module, command_first_word):
    """
    执行模块的命令解析和处理。

    该函数是带命令模板的模块的执行入口，负责：
    1. 使用 CommandParser 解析命令参数
    2. 验证发送者权限（超级用户、管理员等）
    3. 检查命令在当前会话中的有效性（平台限制等）
    4. 根据命令函数的参数签名构建调用参数
    5. 显示“正在输入……”状态（如果用户启用）
    6. 执行命令函数

    :param msg: 消息会话对象
    :param module: 模块对象
    :param command_first_word: 命令的第一个词（模块名）
    """
    bot: "Bot" = exports["Bot"]
    _typing = False  # 标记是否显示“正在输入……”状态
    try:
        # ========== 步骤 1: 解析命令参数 ==========
        command_parser = CommandParser(
            module, msg=msg, module_name=command_first_word, command_prefixes=msg.session_info.prefixes
        )
        try:
            parsed_msg = command_parser.parse(msg.trigger_msg)  # 解析模块的子功能命令
            command: CommandMeta = parsed_msg[0]
            msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
            Logger.trace("Parsed message: " + str(msg.parsed_msg))

            # ========== 步骤 2: 验证发送者权限 ==========

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
                    await msg.send_message(I18NContext("parser.admin.permission.denied.command"))
                    return

            # ========== 步骤 3: 检查命令是否在会话内有效 ==========

            if (
                not command.load
                or msg.session_info.target_from in command.exclude_from
                or msg.session_info.client_name in command.exclude_from
                or (
                    "*" not in command.available_for
                    and msg.session_info.target_from not in command.available_for
                    and msg.session_info.client_name not in command.available_for
                )
            ):
                raise InvalidCommandFormatError

            # ========== 步骤 4: 构建函数参数 ==========
            # 根据命令函数的签名，准备调用参数
            kwargs = {}
            func_params = inspect.signature(command.function).parameters

            if len(func_params) > 1 and msg.parsed_msg:
                # 函数有多个参数，需要映射解析后的参数
                parsed_msg_ = msg.parsed_msg.copy()
                no_message_session = True  # 标记是否缺少 MessageSession 参数

                # 遍历函数的所有参数
                for param_name, param_obj in func_params.items():
                    # ========== 处理 MessageSession 参数 ==========
                    if param_obj.annotation == bot.MessageSession:
                        kwargs[param_name] = msg
                        no_message_session = False

                    # ========== 处理自定义 Param 类型 ==========
                    elif isinstance(param_obj.annotation, Param):
                        if param_obj.annotation.name in parsed_msg_:
                            # 检查类型是否匹配
                            if isinstance(parsed_msg_[param_obj.annotation.name], param_obj.annotation.type):
                                kwargs[param_name] = parsed_msg_[param_obj.annotation.name]
                                del parsed_msg_[param_obj.annotation.name]
                            else:
                                Logger.warning(f"{param_obj.annotation.name} is not a {param_obj.annotation.type}")
                        else:
                            Logger.warning(f"{param_obj.annotation.name} is not in parsed_msg")

                    # ========== 处理普通参数 ==========
                    param_name_ = param_name

                    # 检查是否使用了 <param> 格式
                    if (param_name__ := f"<{param_name}>") in parsed_msg_:
                        param_name_ = param_name__

                    if param_name_ in parsed_msg_:
                        # 参数在解析结果中
                        kwargs[param_name] = parsed_msg_[param_name_]
                        try:
                            # 尝试根据类型注解进行类型转换
                            if param_obj.annotation == int:
                                kwargs[param_name] = int(parsed_msg_[param_name_])
                            elif param_obj.annotation == float:
                                kwargs[param_name] = float(parsed_msg_[param_name_])
                            elif param_obj.annotation == bool:
                                kwargs[param_name] = bool(parsed_msg_[param_name_])
                            del parsed_msg_[param_name_]
                        except (KeyError, ValueError):
                            # 类型转换失败，命令格式错误
                            raise InvalidCommandFormatError
                    else:
                        # 参数不在解析结果中，使用默认值或 None
                        if param_name_ not in kwargs:
                            if param_obj.default is not inspect.Parameter.empty:
                                kwargs[param_name_] = param_obj.default
                            else:
                                kwargs[param_name_] = None

                # 警告：函数缺少 MessageSession 参数（可能导致运行时错误）
                if no_message_session:
                    Logger.warning(
                        f"{command.function.__name__} has no Bot.MessageSession parameter, did you forgot to add it?\n"
                        "Remember: MessageSession IS NOT Bot.MessageSession"
                    )
            else:
                # 函数只有一个参数，直接传入 MessageSession
                kwargs[func_params[list(func_params.keys())[0]].name] = msg

            # ========== 步骤 5: 显示“正在输入……”状态 ==========
            if msg.session_info.target_info.target_data.get("typing_prompt", True):
                await msg.start_typing()
                _typing = True

            # ========== 步骤 6: 执行命令函数 ==========
            await parsed_msg[0].function(**kwargs)

            # 如果函数没有使用 msg.finish，手动结束会话
            raise SessionFinished(msg.sent)
        except InvalidCommandFormatError:
            if not msg.session_info.sender_info.sender_data.get("typo_check", True):
                await msg.send_message(
                    I18NContext(
                        "parser.command.invalid.syntax", module=command_first_word, prefix=msg.session_info.prefixes[0]
                    )
                )
            return
        except Exception as e:
            raise e
    except InvalidHelpDocTypeError:
        Logger.exception()
        await msg.send_message(I18NContext("error.module.helpdoc_invalid", module=command_first_word))
        return
    finally:
        if _typing:
            await msg.end_typing()


async def _process_tos_abuse_warning(msg: "Bot.MessageSession", e: AbuseWarning):
    """
    处理 ToS 滥用警告。

    当检测到用户滥用命令时，根据配置决定是否警告用户并记录违规。

    处理方式：
    - 如果启用了 ToS 且警告次数 >= 1：记录警告并设置临时封禁
    - 否则：显示错误消息但不记录

    :param msg: 消息会话对象
    :param e: 滥用警告异常对象
    """
    if enable_tos and Config("tos_warning_counts", 5) >= 1 and not msg.check_super_user():
        await abuse_warn_target(msg, str(e))
        temp_ban_counter[msg.session_info.sender_id] = {"count": 1, "ts": time.time()}
    else:
        err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
        err_msg_chain.append(Plain(msg.session_info.locale.t_str(str(e))))
        err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
        await msg.send_message(err_msg_chain)


async def _process_send_message_failed(msg: "Bot.MessageSession"):
    """
    处理消息发送失败的情况。

    当机器人无法发送消息时（如被禁言、权限不足等），
    触发错误信号并尝试通知用户。

    :param msg: 消息会话对象
    """
    await msg.handle_error_signal()
    await msg.send_message(I18NContext("error.message.limited"))


async def _process_noreport_exception(msg: "Bot.MessageSession", e: NoReportException):
    """
    处理无需报告的异常。

    这类异常通常是已知的用户错误（如参数错误、权限不足等），
    不需要记录详细的错误报告，只需告知用户。

    :param msg: 消息会话对象
    :param e: 无需报告的异常对象
    """
    Logger.exception()
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg = msg.session_info.locale.t_str(str(e))
    err_msg_chain += match_kecode(err_msg)
    err_msg_chain.append(I18NContext("error.message.prompt.noreport"))
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)


async def _process_external_exception(msg: "Bot.MessageSession", e: Exception):
    """
    处理外部异常（如网络错误、API 错误等）。

    这类异常通常是由外部服务引起的（如 API 不可用、网络超时等），
    需要告知用户问题来源，并提供反馈渠道。

    :param msg: 消息会话对象
    :param e: 外部异常对象
    """
    Logger.exception()
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg = msg.session_info.locale.t_str(str(e))
    err_msg_chain += match_kecode(err_msg)
    err_msg_chain.append(I18NContext("error.message.prompt.external"))
    if bug_report_url:
        err_msg_chain.append(I18NContext("error.message.prompt.address", url=bug_report_url))
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)


async def _process_exception(msg: "Bot.MessageSession", e: Exception):
    """
    处理未预期的内部异常。

    这是最后的异常处理层，用于捕获所有未被其他处理器捕获的异常。
    会记录完整的错误堆栈，通知用户，并将错误报告发送给管理员。

    处理流程：
    1. 记录完整的错误堆栈到日志
    2. 向用户发送错误消息和报告提示
    3. 如果配置了报告目标，发送详细错误报告给管理员

    :param msg: 消息会话对象
    :param e: 异常对象
    """
    bot: "Bot" = exports["Bot"]

    # 获取完整的错误堆栈
    tb = traceback.format_exc()
    Logger.error(tb)

    # 构建用户错误消息
    err_msg_chain = MessageChain.assign(I18NContext("error.message.prompt"))
    err_msg = msg.session_info.locale.t_str(str(e))
    err_msg_chain += match_kecode(err_msg)
    err_msg_chain.append(I18NContext("error.message.prompt.report"))

    # 添加 bug 报告地址
    if bug_report_url:
        err_msg_chain.append(I18NContext("error.message.prompt.address", url=bug_report_url))

    # 触发错误信号并发送消息
    await msg.handle_error_signal()
    await msg.send_message(err_msg_chain)

    # ========== 发送错误报告给管理员 ==========
    if report_targets:
        for target in report_targets:
            # 获取报告目标
            if f := await bot.fetch_target(target):
                # 发送详细的错误报告
                await bot.send_direct_message(
                    f,
                    [
                        I18NContext("error.message.report", command=msg.trigger_msg),
                        Plain(tb.strip(), disable_joke=True),
                    ],
                    enable_parse_message=False,
                    disable_secret_check=True,
                )


async def _command_typo_check(msg: "Bot.MessageSession", modules, command_first_word):
    """
    命令错字检查和纠正。

    该函数实现了智能的错字纠正功能，当用户输入的命令无法匹配时，
    尝试找出最接近的正确命令并询问用户是否需要纠正。

    纠正流程：
    1. 模块名纠正：查找相似的模块名
    2. 命令参数纠正：根据模板匹配相似的命令结构
    3. 可选参数纠正：匹配可选标志和参数
    4. 必需参数纠正：匹配必需参数
    5. 询问用户确认：显示建议的命令并等待确认

    相似度评分：
    - 模块名阈值：typo_check_module_score (默认 0.6)
    - 命令阈值：typo_check_command_score (默认 0.3)
    - 选项阈值：typo_check_options_score (默认 0.3)
    - 参数阈值：typo_check_args_score (默认 0.5)

    :param msg: 消息会话对象
    :param modules: 可用的模块字典
    :param command_first_word: 用户输入的命令第一个词
    :return: (新消息会话, 新命令词, 是否已确认) 元组
             - 如果纠正成功且用户确认，返回新的消息会话
             - 如果用户拒绝或无法纠正，返回 (None, None, confirmed)
    """
    bot: "Bot" = exports["Bot"]

    # ========== 步骤 1: 获取用户权限 ==========
    is_base_superuser = msg.session_info.sender_id in bot.base_superuser_list
    is_superuser = msg.check_super_user()

    # ========== 步骤 2: 收集用户可用的模块列表 ==========
    available_modules = []
    for x in modules:
        # 筛选条件：基础模块或已启用的模块
        if modules[x].base or (x in msg.session_info.enabled_modules):
            # 跳过隐藏模块
            if modules[x].hidden:
                continue
            # 跳过需要超级用户权限的模块（如果用户不是超级用户）
            if modules[x].required_superuser and not is_superuser:
                continue
            # 跳过需要基础超级用户权限的模块
            if modules[x].required_base_superuser and not is_base_superuser:
                continue
            available_modules.append(x)

    # ========== 步骤 3: 模块名相似度匹配 ==========
    # 使用 difflib 找出最接近的模块名
    match_close_module: list = difflib.get_close_matches(
        command_first_word, available_modules, 1, typo_check_module_score
    )

    if match_close_module:
        # 找到了相似的模块
        Logger.debug(f"Match module: {command_first_word} -> {match_close_module[0]}")
        module: Module = modules[match_close_module[0]]

        # ========== 步骤 4: 检查模块是否有命令模板 ==========
        none_template = True
        for func in module.command_list.get(msg.session_info.target_from):
            if func.command_template:
                none_template = False
                break

        command_split = msg.trigger_msg.split(" ")
        len_command_split = len(command_split)

        # ========== 步骤 5: 命令参数匹配（仅对有模板的模块）==========
        if not none_template and len_command_split > 1:
            get_commands: list[CommandMeta] = module.command_list.get(msg.session_info.target_from)

            # 根据参数数量对命令模板分组
            # 格式: [参数数量 -> [模板列表]]
            command_templates = {}
            for func in get_commands:
                command_template: list[argsTemplate] = copy.deepcopy(func.command_template)
                for ct in command_template:
                    # 只保留 ArgumentPattern（过滤描述等）
                    ct.args_ = [a for a in ct.args if isinstance(a, ArgumentPattern)]
                    if (len_args := len(ct.args)) not in command_templates:
                        command_templates[len_args] = [ct]
                    else:
                        command_templates[len_args].append(ct)

            # ========== 步骤 6: 选择最合适的命令模板组 ==========
            if len_command_split - 1 > len(command_templates):
                # 用户输入的参数比所有模板都多，选择参数最多的模板
                select_templates = command_templates[max(command_templates)]
            else:
                try:
                    # 选择参数数量刚好匹配的模板组
                    select_templates = command_templates[len_command_split - 1]
                except KeyError:
                    # 没有精确匹配，找一个最接近的
                    select_templates = command_templates[
                        max(command_templates.keys(), key=lambda k: min(abs(k - (len_command_split - 1)), k))
                    ]

            # ========== 步骤 7: 命令字符串相似度匹配 ==========
            match_close_command: list = difflib.get_close_matches(
                " ".join(command_split[1:]), templates_to_str(select_templates), 1, typo_check_command_score
            )

            if match_close_command:
                # 找到了相似的命令
                Logger.debug(f"Match command: {' '.join(command_split[1:])} -> {match_close_command[0]}")
                match_split = match_close_command[0]

                # ========== 步骤 8: 分离可选参数 ==========
                # 切割可选参数（[...]）和必需参数
                m_split_options = filter(None, re.split(r"(\[.*?\])", match_split))
                old_command_split = command_split.copy()
                del old_command_split[0]  # 删除模块名
                new_command_split = [match_close_module[0]]
                for m_ in m_split_options:
                    if m_.startswith("["):  # 如果是可选参数
                        m_split = m_.split(" ")  # 切割可选参数中的空格（说明存在多个子必须参数）
                        if len(m_split) > 1:
                            match_close_options = difflib.get_close_matches(
                                m_split[0][1:], old_command_split, 1, typo_check_options_score
                            )  # 进一步匹配可选参数
                            if match_close_options:
                                Logger.debug(f"Match close options: {m_split[0][1:]} -> {match_close_options[0]}")
                                position = old_command_split.index(match_close_options[0])  # 定位可选参数的位置
                                new_command_split.append(m_split[0][1:])  # 将可选参数插入到新命令列表中
                                new_command_split += old_command_split[position + 1 : position + len(m_split)]
                                del old_command_split[position : position + len(m_split)]  # 删除原命令列表中的可选参数
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
                                        old_command_split[0], [mm], 1, typo_check_args_score
                                    )  # 进一步匹配参数
                                    if match_close_args:
                                        Logger.debug(
                                            f"Match close args: {old_command_split[0]} -> {match_close_args[0]}"
                                        )
                                        new_command_split.append(mm)
                                        del old_command_split[0]
                                    else:
                                        new_command_split.append(old_command_split[0])
                                        del old_command_split[0]
                            else:
                                new_command_split.append(mm)
                new_command_display = " ".join(new_command_split)
                if new_command_display != msg.trigger_msg:
                    wait_confirm = await msg.wait_confirm(
                        I18NContext(
                            "parser.command.fixup.confirm",
                            command=f"{msg.session_info.prefixes[0]}{new_command_display}",
                        )
                    )
                    if wait_confirm:
                        command_first_word = new_command_split[0]
                        msg.trigger_msg = " ".join(new_command_split)
                        return msg, command_first_word, True
                    return None, None, True
            else:
                if len_command_split - 1 == 1:
                    new_command_display = f"{match_close_module[0]} {' '.join(command_split[1:])}"
                    if new_command_display != msg.trigger_msg:
                        wait_confirm = await msg.wait_confirm(
                            I18NContext(
                                "parser.command.fixup.confirm",
                                command=f"{msg.session_info.prefixes[0]}{new_command_display}",
                            )
                        )
                        if wait_confirm:
                            command_first_word = match_close_module[0]
                            msg.trigger_msg = " ".join([match_close_module[0]] + command_split[1:])
                            return msg, command_first_word, True
                        return None, None, True
        else:
            new_command_display = (
                f"{match_close_module[0] + (' ' + ' '.join(command_split[1:]) if len(command_split) > 1 else '')}"
            )
            if new_command_display != msg.trigger_msg:
                wait_confirm = await msg.wait_confirm(
                    I18NContext(
                        "parser.command.fixup.confirm", command=f"{msg.session_info.prefixes[0]}{new_command_display}"
                    )
                )
                if wait_confirm:
                    command_first_word = match_close_module[0]
                    msg.trigger_msg = match_close_module[0]
                    return msg, command_first_word, True
                return None, None, True
    return None, None, False


__all__ = ["parser"]
