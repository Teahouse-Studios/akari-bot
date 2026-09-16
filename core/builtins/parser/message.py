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

import functools
import inspect
import time
from types import UnionType
from typing import TYPE_CHECKING, Union, get_args, get_origin

from core.builtins.message.internal import I18NContext
from core.builtins.parser.command import CommandParser
from core.builtins.parser.hooks import (
    Continue,
    Handled,
    HookPoint,
    RecoveryProposal,
    Stop,
    StopScope,
    dispatch_parser_hook,
    has_hook_subscribers,
)
from core.builtins.session.lock import ExecutionLockList
from core.builtins.session.tasks import SessionTaskManager
from core.constants.exceptions import (
    AbuseWarning,
    ExternalException,
    InvalidCommandFormatError,
    NoReportException,
    SessionFinished,
    SendMessageFailed,
    WaitCancelException,
)
from core.exports import exports
from core.loader import ModulesManager
from core.logger import Logger
from core.module_runtime import ModuleRuntimeManager
from core.types import Module, Param
from core.types.module.component_meta import CommandMeta
from core.utils.container import ExpiringTempDict
from core.utils.func import normalize_space

if TYPE_CHECKING:
    from core.builtins.bot import Bot

# 匹配哈希缓存 - 缓存消息与模块的匹配结果，加速处理
match_hash_cache = ExpiringTempDict()

# 标记为单次触发的正则，其「模块名 + 正则序号 + 场景 ID」在此登记，登记后不再参与匹配。
# 仅存于进程内存，重启即清空；条目数上限为「触发过的场景数 × 单次触发正则条数」，有界。
regex_once_cache: set[tuple[str, int, str]] = set()


async def _dispatch_stage(
    point: HookPoint,
    msg: "Bot.MessageSession",
    *,
    module_name: str | None = None,
    command_first_word: str | None = None,
    data: dict | None = None,
) -> Continue | Stop | RecoveryProposal | Handled:
    """分发入口 hook 并应用控制结果。

    无订阅时短路，避免每条消息空跑 executor。
    """
    if not has_hook_subscribers(point):
        return Continue()
    outcome = await dispatch_parser_hook(
        point,
        msg,
        module_name=module_name,
        command_first_word=command_first_word,
        data=data,
    )
    result = outcome.result
    if isinstance(result, Continue):
        return result

    if isinstance(result, Stop):
        if result.message is not None:
            await msg.send_message(result.message)
        return result

    return result


async def _dispatch_execution_error(
    msg: "Bot.MessageSession",
    error: BaseException,
    *,
    module_name: str | None,
    module_type: str,
    error_kind: str | None = None,
) -> None:
    """把执行异常交给错误策略；核心只负责分类和分发。"""
    data = {"error": error, "module_type": module_type}
    if error_kind is not None:
        data["error_kind"] = error_kind
    outcome = await _dispatch_stage(
        HookPoint.EXECUTION_ERROR,
        msg,
        module_name=module_name,
        command_first_word=module_name,
        data=data,
    )
    if not isinstance(outcome, Handled):
        Logger.exception(f"Unhandled parser execution error in module {module_name or '<unknown>'}.")


async def _validate_recovery_target(
    msg: "Bot.MessageSession",
    modules,
    command_first_word: str,
    trigger_msg: str,
) -> bool:
    """确认后重校验：模块仍在、已加载、平台可用、模板仍可解析。"""
    module = modules.get(command_first_word)
    if module is None or not module._db_load:
        return False
    has_template = any(func.command_template for func in module.command_list.get(msg.session_info.target_from))
    # 有命令模板但当前客户端解析不出可用命令，视为过期建议；无模板模块允许透传
    if has_template and not _command_available_for_current_session(msg, module, command_first_word):
        return False
    # 场景启用：非 base 且要求启用时，确认期间被禁用则放弃
    if not module.base and msg.session_info.require_enable_modules:
        if command_first_word not in msg.session_info.enabled_modules:
            return False
    return True


async def _try_command_recovery(
    msg: "Bot.MessageSession",
    modules,
    command_first_word: str,
    identify_str: str,
    *,
    unmatched_kind: str = "module",
) -> bool:
    """处理未匹配命令：请求恢复建议，确认后按最新注册表重解析并执行。

    :param unmatched_kind: ``module`` 未找到模块；``template`` 模块存在但模板不匹配。
    :return: True 表示已消费本次恢复路径。
    """
    proposal_result = await _dispatch_stage(
        HookPoint.COMMAND_UNMATCHED,
        msg,
        command_first_word=command_first_word,
        data={"modules": dict(modules), "unmatched_kind": unmatched_kind},
    )
    if isinstance(proposal_result, Handled):
        # 扩展已处理，不再发默认提示
        return True
    if isinstance(proposal_result, Stop):
        # message 已由 _dispatch_stage 发送
        return True
    proposal = proposal_result if isinstance(proposal_result, RecoveryProposal) else None

    if proposal is not None:
        display = proposal.display or proposal.trigger_msg
        if display != msg.trigger_msg:
            wait_confirm = await msg.wait_confirm(
                I18NContext(
                    "parser.command.fixup.confirm",
                    command=f"{msg.session_info.prefixes[0]}{display}",
                )
            )
            if wait_confirm:
                # 确认期间可能热重载/权限变化：从最新注册表取模块并重校验
                fresh_modules = ModulesManager.return_modules_list(
                    msg.session_info.target_from, msg.session_info.client_name, use_cache=False
                )
                msg.trigger_msg = proposal.trigger_msg
                new_word = proposal.command_first_word
                # 等待期间管理员可能已停用模块、静音或改权限；仅模块表不是权威状态。
                # 刷新 Union 派生状态（enabled_modules/muted/权限等），同时保留本次消息
                # 已生效的前缀与 hook 草稿修改，避免直接 refresh 丢掉入口覆盖值。
                try:
                    await msg.session_info.refresh_info()
                except Exception:
                    Logger.exception("Failed to refresh session info during command recovery; aborting recovery.")
                    return True
                if not await _validate_recovery_target(msg, fresh_modules, new_word, proposal.trigger_msg):
                    await _dispatch_stage(
                        HookPoint.COMMAND_UNMATCHED,
                        msg,
                        command_first_word=new_word,
                        data={"unmatched_kind": "module", "recovery_stale": True},
                    )
                    return True
                await _execute_module(msg, fresh_modules, new_word, identify_str, allow_recovery=False)
                return True
            # 用户拒绝：不再追加无效提示
            return True

    if unmatched_kind == "template":
        # 默认语法提示由 parser_policies 的 COMMAND_UNMATCHED 订阅负责。
        return True
    # 默认模块不存在提示同样由策略订阅负责。
    return True


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
    1. 刷新用户和场景信息（从数据库）
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
    try:
        # 入站策略（忽略发送者、互认机器人、封禁/阻断身份）在等待任务投递前统一处理。
        ready_result = await _dispatch_stage(HookPoint.SESSION_READY, msg)
        if isinstance(ready_result, Stop) and ready_result.scope == StopScope.MESSAGE:
            return

        # ========== 步骤 2: 检查任务队列 ==========
        # 检查是否有等待此消息的任务（如等待用户回复）。入口策略可以明确让出等待路由，
        # 但仍允许消息继续进入普通命令/正则流程。
        wait_result = await _dispatch_stage(HookPoint.SESSION_BEFORE_WAIT, msg)
        if isinstance(wait_result, Stop) and wait_result.scope == StopScope.MESSAGE:
            return
        skip_wait_tasks = isinstance(wait_result, Stop) or (
            isinstance(wait_result, Continue) and wait_result.data.get("skip_wait_tasks", False)
        )
        if not skip_wait_tasks:
            # 消息已被等待任务或 callback 消费：它属于先前命令的执行域，
            # 不能再次进入命令/正则路由，否则会与持有锁的根命令形成自锁。
            if await SessionTaskManager.check(msg):
                return

        # 获取该平台和客户端的所有可用模块
        modules = ModulesManager.return_modules_list(msg.session_info.target_from, msg.session_info.client_name)

        # 将消息转换为易读的显示格式
        msg.trigger_msg = normalize_space(msg.as_display())

        normalized_result = await _dispatch_stage(HookPoint.MESSAGE_NORMALIZED, msg)
        if isinstance(normalized_result, Stop):
            return

        # 如果消息为空，直接返回
        if len(msg.trigger_msg) == 0:
            return

        # 如果消息中有需要过滤的词，直接返回
        # if contain_badwords(msg.trigger_msg):
        #     return

        # ========== 步骤 3: 命令匹配 ==========
        # 检查消息是否以命令前缀开头
        disable_prefix, in_prefix_list = _get_prefixes(msg)

        if in_prefix_list or disable_prefix:  # 检查消息前缀，注意此时 log 的 msg.trigger_msg 是带前缀的
            Logger.info(f"{identify_str} -> [Bot]: {msg.trigger_msg}")

            command_first_word = await _process_command(msg, modules, disable_prefix, in_prefix_list)

            routed_command_available = None
            if command_first_word in modules:
                routed_command_available = _command_available_for_current_session(
                    msg, modules[command_first_word], command_first_word
                )

            route_result = await _dispatch_stage(
                HookPoint.COMMAND_ROUTE,
                msg,
                module_name=command_first_word,
                command_first_word=command_first_word,
                data={"routed_command_available": routed_command_available},
            )
            if isinstance(route_result, Stop):
                return

            claim_outcome = await _dispatch_stage(
                HookPoint.CHANNEL_CLAIM,
                msg,
                module_name=command_first_word,
                command_first_word=command_first_word,
                data={"routed_command_available": routed_command_available},
            )
            if isinstance(claim_outcome, Stop):
                return

            if command_first_word:
                if not await try_acquire_execution_lock(msg):
                    await _dispatch_stage(
                        HookPoint.COMMAND_BEFORE_EXECUTE,
                        msg,
                        command_first_word=command_first_word,
                        data={"locked": True},
                    )
                    return

            if command_first_word in modules:  # 检查触发命令是否在模块列表中
                if modules[command_first_word]._db_load:  # 检查模块是否已加载
                    await _execute_module(msg, modules, command_first_word, identify_str)
                else:
                    await _dispatch_stage(
                        HookPoint.COMMAND_UNMATCHED,
                        msg,
                        command_first_word=command_first_word,
                        data={"unmatched_kind": "unloaded"},
                    )
            else:
                await _try_command_recovery(msg, modules, command_first_word, identify_str)
            return msg

        # 正则路由策略（禁用前缀、静音、运行中提醒）由 core policy hook 决定。
        regex_route_result = await _dispatch_stage(HookPoint.REGEX_ROUTE, msg)
        if isinstance(regex_route_result, Stop):
            return msg

        await _execute_regex(msg, modules, identify_str)
        return msg

    except WaitCancelException:  # 出现于等待被取消的情况
        Logger.warning("Waiting task cancelled by user.")

    except Exception:
        Logger.exception()
    finally:
        try:
            await msg.release_execution_resources()
        finally:
            # wait_* 的回复会话会共享根命令的 ExecutionState，但没有最终
            # 清理所有权。它仍可在 continuation 内主动 sleep／wait，从而
            # 释放和重获同一 lease；这里只能由原始 parser 释放最终 lease，
            if getattr(msg, "_execution_state_owner", True):
                ExecutionLockList.remove(msg)
            await _dispatch_stage(HookPoint.FINISHED, msg)


def _command_available_for_current_session(msg: "Bot.MessageSession", module: Module, command_first_word: str) -> bool:
    """判断当前客户端能否解析一个按平台分流的具体命令。"""
    command_parser = CommandParser(
        module, msg=msg, module_name=command_first_word, command_prefixes=msg.session_info.prefixes
    )
    try:
        parsed = command_parser.parse(msg.trigger_msg)
    except InvalidCommandFormatError:
        return False
    return bool(parsed and parsed[0])


def _get_prefixes(msg: "Bot.MessageSession"):
    """
    检查并处理消息的命令前缀。

    该函数检查禁用前缀配置、匹配消息前缀，并把命中的前缀移到列表首位。

    :param msg: 消息会话对象
    :return: (disable_prefix, in_prefix_list) 元组
             - disable_prefix: 是否禁用前缀检查（True 表示任何消息都视为命令）
             - in_prefix_list: 消息是否以某个前缀开头
    """
    disable_prefix = False
    # 如果上游指定了命令前缀，使用指定的命令前缀
    if msg.session_info.prefixes:
        # 如果前缀列表中包含空字符串，表示禁用前缀检查
        if "" in msg.session_info.prefixes:
            disable_prefix = True

    display_prefix = ""
    in_prefix_list = False

    for cp in msg.session_info.prefixes:
        if msg.trigger_msg.startswith(cp):
            display_prefix = cp
            in_prefix_list = True
            break

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
        cmd_words = command_split

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
    first_word = command_split[0]
    if alias_list:
        # 选择最长的别名（避免短别名误匹配）
        max_alias = str(max(alias_list, key=len))
        # 获取别名对应的实际模块名
        real_name = ModulesManager.modules_aliases[max_alias]

        # 重构命令：实际模块名 + 别名后的剩余参数
        command_words = real_name.split(" ") + command_split[len(max_alias.split(" ")) :]
        command = " ".join(command_words)
        first_word = real_name.split(" ")[0]

    # 更新消息的触发命令
    msg.trigger_msg = command

    # 返回命令的第一个词（模块名）
    return first_word


async def _execute_module(
    msg: "Bot.MessageSession",
    modules,
    command_first_word,
    identify_str,
    *,
    allow_recovery: bool = True,
):
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
    :param allow_recovery: 是否允许模板不匹配时走纠错恢复；恢复重入应传 False
    """
    time_start = time.perf_counter()
    _typing = False  # 标记是否正在显示“正在输入……”状态
    try:
        module: Module = modules[command_first_word]

        # ========== 步骤 1: 入口 prepare（策略与 ToS）==========
        prepare_result = await _dispatch_stage(
            HookPoint.COMMAND_PREPARE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"module": module},
        )
        if isinstance(prepare_result, Stop):
            return

        # ========== 步骤 2: 入口 before_parse（ToS 令牌桶等）==========
        before_parse_result = await _dispatch_stage(
            HookPoint.COMMAND_BEFORE_PARSE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"base": module.base},
        )
        if isinstance(before_parse_result, Stop):
            return

        # ========== 步骤 3: 检查并处理命令模板 ==========
        none_templates = True  # 标记模块是否有命令模板
        for func in module.command_list.get(msg.session_info.target_from):
            if func.command_template:
                none_templates = False
                break

        if not none_templates:
            # 有命令模板，进行命令解析
            command_result = await _execute_module_command(msg, module, command_first_word)
            if command_result is not False:
                # ``None`` 表示命令已被入口策略处理（例如权限拒绝或参数错误），
                # 不应伪装成成功执行；正常命令会在 helper 内抛出 SessionFinished。
                return
            # 仅模板匹配失败进入恢复；参数转换或已开始执行的命令报错不能重试。
            if module.suppress_invalid_prompt:
                return
        else:
            # ========== 步骤 4: 无模板，直接传递消息 ==========
            # 模块没有命令模板，直接将消息传给模块处理
            msg.parsed_msg = None
            for func in module.command_list.set:
                if not func.command_template:
                    # 显示“正在输入……”状态（如果用户启用）
                    if msg.session_info.typing_prompt_enabled:
                        await msg.start_typing()
                        _typing = True
                    # 执行模块函数
                    async with ModuleRuntimeManager.use(module.module_name):
                        await func.function(msg)
                    raise SessionFinished(msg.sent)

        # ========== 步骤 5: 模板未匹配时的恢复建议 ==========
        if allow_recovery:
            await _try_command_recovery(msg, modules, command_first_word, identify_str, unmatched_kind="template")
        else:
            await _dispatch_stage(
                HookPoint.COMMAND_UNMATCHED,
                msg,
                command_first_word=command_first_word,
                data={"unmatched_kind": "syntax", "suppress_invalid_prompt": module.suppress_invalid_prompt},
            )
    except SendMessageFailed as e:
        await _dispatch_execution_error(msg, e, module_name=command_first_word, module_type="normal")

    # ========== 异常处理 ==========
    except SessionFinished as e:
        # 会话正常结束
        time_used = time.perf_counter() - time_start
        Logger.success(
            f"Successfully finished session from {identify_str}, returns: {str(e)}. Times take up: {time_used:06f}s"
        )
        await _dispatch_stage(
            HookPoint.EXECUTION_FINISHED,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"module_name": command_first_word, "module_type": "normal"},
        )

    except ExternalException as e:
        await _dispatch_execution_error(msg, e, module_name=command_first_word, module_type="normal")

    except AbuseWarning as e:
        await _dispatch_execution_error(msg, e, module_name=command_first_word, module_type="normal")

    except NoReportException as e:
        await _dispatch_execution_error(msg, e, module_name=command_first_word, module_type="normal")

    except Exception as e:
        # 其他未预期的异常
        error_kind = "external" if "timeout" in str(e).lower().replace(" ", "") else None
        await _dispatch_execution_error(
            msg,
            e,
            module_name=command_first_word,
            module_type="normal",
            error_kind=error_kind,
        )
    finally:
        # 清理工作
        if _typing:
            # 结束“正在输入……”状态
            await msg.end_typing()
        # 释放执行锁
        ExecutionLockList.remove(msg)


def regex_once_triggered(module_name: str, index: int, target_id: str) -> bool:
    """
    判断一条标记为单次触发的正则是否已在该场景中跑过。

    :param module_name: 所属模块名称。
    :param index: 该正则在模块 ``regex_list`` 中的序号。
    :param target_id: 场景 ID。
    :return: 是否已触发过。
    """
    return (module_name, index, target_id) in regex_once_cache


def mark_regex_once(module_name: str, index: int, target_id: str) -> None:
    """
    登记一条单次触发的正则已在该场景中跑过。

    :param module_name: 所属模块名称。
    :param index: 该正则在模块 ``regex_list`` 中的序号。
    :param target_id: 场景 ID。
    """
    regex_once_cache.add((module_name, index, target_id))


def regex_module_enabled(
    module: "Module", module_name: str, enabled_modules: list | None, read_all_messages: bool = True
) -> bool:
    """
    判断一个模块的正则处理函数是否应当参与匹配。

    base 模块无须在场景中启用即可生效，与命令路径 :func:`_execute_module` 的判定保持一致。
    此前该豁免仅存在于命令路径，导致 base 模块注册的正则永远不会触发。

    权限判定置于启用判定之前：模块可能在权限开启期间被启用，其后权限又被关闭，此时
    ``enabled_modules`` 中仍留有该模块，只拦截启用入口并不足够。

    :param module: 待判定的模块。
    :param module_name: 模块名称。
    :param enabled_modules: 当前场景已启用的模块列表。
    :param read_all_messages: 机器人在该场景是否有权限读取全部消息。
    :return: 是否参与匹配。
    """
    if module.base:
        return True
    if module.regex and not read_all_messages:
        return False
    return bool(enabled_modules) and module_name in enabled_modules


async def try_acquire_execution_lock(msg: "Bot.MessageSession") -> bool:
    """
    尝试为当前会话获取执行锁。

    获取失败表示该会话已有命令在执行。指令路径应就此告知用户，正则路径则应静默跳过：
    正则由消息内容隐式触发，用户并未主动请求，提示对其纯属噪音。

    :param msg: 消息会话。
    :return: 是否成功获取。
    """
    return await ExecutionLockList.acquire(msg)


def regex_func_available(rfunc, target_from: str, client_name: str) -> bool:
    """
    判断一条正则处理函数在当前平台上是否可用。

    判据与 :meth:`RegexMatches.get` 一致。此前 :func:`_execute_regex` 直接遍历 ``regex_list.set``，
    只校验模块级的 ``available_for``，正则级的平台声明因而从未生效——注册时写下的
    ``@module.regex(available_for=...)`` 形同虚设。

    :param rfunc: 正则处理函数的元数据。
    :param target_from: 当前场景的前缀。
    :param client_name: 当前客户端名称。
    :return: 是否可用。
    """
    if not rfunc.load:
        return False
    if target_from in rfunc.exclude_from or client_name in rfunc.exclude_from:
        return False
    return "*" in rfunc.available_for or target_from in rfunc.available_for or client_name in rfunc.available_for


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
    # 同一条消息会被所有模块的正则轮流匹配，而渲染结果只由这两个参数决定，
    # 按参数缓存一次，避免每条正则都把消息链重新走一遍
    display_cache: dict[tuple[bool, tuple], str] = {}

    def get_trigger_msg(text_only: bool, element_filter) -> str:
        cache_key = (text_only, tuple(element_filter or ()))
        if cache_key not in display_cache:
            display_cache[cache_key] = msg.as_display(text_only=text_only, element_filter=element_filter)
        return display_cache[cache_key]

    # ========== 遍历所有模块 ==========
    for m in modules:
        # 跳过未加载的模块
        if not modules[m]._db_load:
            continue

        try:
            # ========== 步骤 1: 检查模块是否已启用且有正则表达式 ==========
            if (
                regex_module_enabled(
                    modules[m], m, msg.session_info.enabled_modules, msg.session_info.read_all_messages
                )
                and modules[m].regex_list.set
            ):
                regex_module: Module = modules[m]

                # ========== 步骤 2: 检查模块可用性和平台限制 ==========
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

                candidate_result = await _dispatch_stage(
                    HookPoint.REGEX_CANDIDATE,
                    msg,
                    module_name=m,
                    data={"module": regex_module},
                )
                if isinstance(candidate_result, Stop):
                    if candidate_result.scope == StopScope.MESSAGE:
                        return
                    continue

                # ========== 步骤 3: 遍历模块的所有正则表达式 ==========
                for index, rfunc in enumerate(regex_module.regex_list.set):
                    # 正则级的平台声明，与命令级的 available_for / exclude_from 对称。
                    # 步骤 3 校验的是模块级声明，两者互不覆盖。
                    if not regex_func_available(rfunc, msg.session_info.target_from, msg.session_info.client_name):
                        continue

                    # 单次触发的正则在该场景跑过之后不再参与匹配，避免每条消息都付出
                    # 通道认领的数据库查询与统计插入。
                    if rfunc.trigger_once_startup and regex_once_triggered(m, index, msg.session_info.target_id):
                        continue

                    time_start = time.perf_counter()
                    matched = False  # 标记是否匹配成功
                    _typing = False  # 标记是否显示“正在输入……”
                    try:
                        matched_hash = 0  # 用于检测重复匹配

                        # 获取要匹配的消息文本（可能只包含纯文本或过滤特定元素）
                        trigger_msg = get_trigger_msg(rfunc.text_only, rfunc.element_filter)

                        # ========== 步骤 5: 执行正则表达式匹配 ==========
                        # mode 与模式均在注册期归一化/编译，此处直接用
                        if rfunc.mode in ("M", "MATCH"):
                            # 使用 match（从字符串开头匹配）
                            msg.matched_msg = rfunc.compiled.match(trigger_msg)
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg.groups())
                        elif rfunc.mode in ("A", "FINDALL"):
                            # 使用 findall（查找所有匹配）
                            msg.matched_msg = tuple(set(rfunc.compiled.findall(trigger_msg)))
                            if msg.matched_msg:
                                matched = True
                                matched_hash = hash(msg.matched_msg)

                        # ========== 步骤 6: 处理匹配成功的情况 ==========
                        if matched:
                            # 记录日志
                            if rfunc.logging:
                                Logger.info(f"{identify_str} -> [Bot]: {msg.trigger_msg}")
                            Logger.debug("Matched hash:" + str(matched_hash))

                            # ========== 循环匹配检测 ==========
                            # 检查是否重复匹配
                            if rfunc.logging and matched_hash in match_hash_cache[msg.session_info.target_id]:
                                Logger.warning("Match loop detected, skipping...")
                                continue

                            # 记录匹配哈希到缓存
                            match_hash_cache[msg.session_info.target_id][matched_hash] = ExpiringTempDict(
                                exp=1, root=False
                            )

                            # ========== 入口 prepare / 冷却 / 权限 ==========
                            prepare_result = await _dispatch_stage(
                                HookPoint.REGEX_PREPARE,
                                msg,
                                module_name=m,
                                data={
                                    "show_typing": rfunc.show_typing,
                                    "base": regex_module.base,
                                    "regex": rfunc,
                                },
                            )
                            if isinstance(prepare_result, Stop):
                                if prepare_result.scope == StopScope.MESSAGE:
                                    return
                                continue

                            # 策略通过后再认领通道，未授权正则不会阻塞其它场景。
                            claim_outcome = await _dispatch_stage(
                                HookPoint.CHANNEL_CLAIM,
                                msg,
                                module_name=m,
                                data={"claim_key": str(matched_hash), "regex": rfunc},
                            )
                            if isinstance(claim_outcome, Stop):
                                if claim_outcome.scope == StopScope.MESSAGE:
                                    return
                                continue
                            # ========== 入口 before_execute（ToS 计数）==========
                            before_exec_result = await _dispatch_stage(
                                HookPoint.REGEX_BEFORE_EXECUTE,
                                msg,
                                module_name=m,
                                data={"show_typing": rfunc.show_typing, "base": regex_module.base},
                            )
                            if isinstance(before_exec_result, Stop):
                                if before_exec_result.scope == StopScope.MESSAGE:
                                    return
                                continue

                            # 正则由消息内容隐式触发，锁被占用时静默跳过；
                            # 此处若发出提示并 return，还会连带中断后续模块的正则遍历。
                            if not await try_acquire_execution_lock(msg):
                                continue

                            # 标记须在调用处理函数之前落下：处理函数为协程，其执行期间同一场景的
                            # 下条消息若到达，标记尚未设置便会重复触发。抛异常时同样保留标记——
                            # 下游链路本就有问题，再次触发只是白费开销。
                            if rfunc.trigger_once_startup:
                                mark_regex_once(m, index, msg.session_info.target_id)

                            if rfunc.show_typing and msg.session_info.typing_prompt_enabled:
                                await msg.start_typing()
                                _typing = True
                                async with ModuleRuntimeManager.use(regex_module.module_name):
                                    await rfunc.function(msg)  # 将msg传入下游模块

                            else:
                                async with ModuleRuntimeManager.use(regex_module.module_name):
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

                        await _dispatch_stage(
                            HookPoint.EXECUTION_FINISHED,
                            msg,
                            module_name=m,
                            data={"module_name": m, "module_type": "regex"},
                        )
                        continue

                    except ExternalException as e:
                        await _dispatch_execution_error(msg, e, module_name=m, module_type="regex")

                    except NoReportException as e:
                        await _dispatch_execution_error(msg, e, module_name=m, module_type="regex")

                    except AbuseWarning as e:
                        await _dispatch_execution_error(msg, e, module_name=m, module_type="regex")

                    except Exception as e:
                        error_kind = "external" if "timeout" in str(e).lower().replace(" ", "") else None
                        await _dispatch_execution_error(
                            msg, e, module_name=m, module_type="regex", error_kind=error_kind
                        )
                    finally:
                        if _typing:
                            await msg.end_typing()
                        ExecutionLockList.remove(msg)

        except SendMessageFailed as e:
            await _dispatch_execution_error(msg, e, module_name=m, module_type="regex")
            continue


@functools.lru_cache(maxsize=256)
def _get_cached_signature(func):
    """缓存 inspect.signature 的结果，避免每次命令执行都做内省。"""
    return inspect.signature(func)


def _unwrap_optional(annotation):
    """取出 ``X | None`` 或 ``Optional[X]`` 中的实际类型。

    可选参数标注为 ``int | None`` 时仍应按 ``int`` 做类型转换，
    否则值会以原始字符串形式传入命令函数。

    :param annotation: 参数的类型注解。
    :return: 剥去 None 后的类型；非 Optional 标注则原样返回。
    """
    if get_origin(annotation) in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _unwrap_option_value(value):
    """解包带杠选项的解析结果，方便直接作为函数参数传入。

    带子参数的选项（如 ``[--foo <bar>]``）在 ``msg.parsed_msg`` 中会被解析为字典
    （形如 ``{"<bar>": "value"}``）。恰好只有一个子参数时解包为该子参数的值，
    使函数参数可以直接拿到 ``"value"``；其余情况原样返回。

    :param value: 选项在 ``msg.parsed_msg`` 中的值。
    :return: 解包后的选项值。
    """
    if isinstance(value, dict) and len(value) == 1:
        return next(iter(value.values()))
    return value


def _resolve_parsed_value(param_name: str, parsed_msg: dict):
    """在解析结果中查找与命令函数参数对应的值。

    查找顺序如下，命中即返回：

    1. ``<param_name>``：位置参数；
    2. ``param_name``：无杠标志或子命令；
    3. ``-param_name`` / ``--param-name``：带杠选项，参数名中的下划线按连字符匹配
       （如参数 ``no_cover`` 对应 ``--no-cover``），带子参数的选项按
       :func:`_unwrap_option_value` 解包；
    4. 带杠选项的子参数 ``<param_name>``：如 ``[-p <page>]`` 对应参数 ``page``。

    :param param_name: 命令函数的参数名。
    :param parsed_msg: ``msg.parsed_msg`` 映射后的解析结果。
    :return: ``(found, value)`` 二元组；``found`` 为假时应使用参数默认值。
    """
    if (key := f"<{param_name}>") in parsed_msg:
        return True, parsed_msg[key]

    if param_name in parsed_msg:
        return True, parsed_msg[param_name]

    option_name = param_name.replace("_", "-")
    for key in (f"-{option_name}", f"--{option_name}"):
        if key in parsed_msg:
            return True, _unwrap_option_value(parsed_msg[key])

    sub_key = f"<{param_name}>"
    for key, value in parsed_msg.items():
        if key.startswith("-") and isinstance(value, dict) and sub_key in value:
            return True, value[sub_key]

    return False, None


def _build_command_kwargs(command, msg: "Bot.MessageSession", bot) -> dict:
    """根据命令函数的签名构建调用参数。

    将 ``msg.parsed_msg`` 的解析结果映射为函数的关键字参数：

    - 标注为 ``Bot.MessageSession`` 的参数注入会话对象；
    - 标注为 ``Param`` 的参数按 ``Param.name`` 取解析结果，适用于
      ``-i``、``<address:port>`` 等无法作为函数参数名的模板元素；
    - 其余参数按 :func:`_resolve_parsed_value` 取位置参数或带杠选项的值。
      选项未提供时（解析结果为 ``False``）对非 ``bool`` 参数回退到默认值，
      标注为 ``bool`` 时直接传入 ``False``。

    :param command: 匹配到的 ``CommandMeta``。
    :param msg: 消息会话对象。
    :param bot: ``Bot`` 类，用于判断 ``Bot.MessageSession`` 标注。
    :return: 调用命令函数用的关键字参数字典。
    :raises InvalidCommandFormatError: 参数存在但无法转换为标注的类型时抛出。
    """
    kwargs = {}
    func_params = _get_cached_signature(command.function).parameters

    if len(func_params) > 1 and msg.parsed_msg:
        parsed_msg_ = msg.parsed_msg
        no_message_session = True

        for param_name, param_obj in func_params.items():
            # ========== 处理 MessageSession 参数 ==========
            if param_obj.annotation == bot.MessageSession:
                kwargs[param_name] = msg
                no_message_session = False
                continue

            # ========== 处理自定义 Param 类型 ==========
            if isinstance(param_obj.annotation, Param):
                if param_obj.annotation.name in parsed_msg_:
                    if isinstance(parsed_msg_[param_obj.annotation.name], param_obj.annotation.type):
                        kwargs[param_name] = parsed_msg_[param_obj.annotation.name]
                    else:
                        Logger.warning(f"{param_obj.annotation.name} is not a {param_obj.annotation.type}")
                elif param_obj.default is inspect.Parameter.empty:
                    # 已声明默认值（如可选选项缺席）时无需提示，避免每次执行都告警
                    Logger.warning(f"{param_obj.annotation.name} is not in parsed_msg")
                if param_name not in kwargs:
                    # 解析结果缺失或类型不匹配时回退到默认值
                    if param_obj.default is not inspect.Parameter.empty:
                        kwargs[param_name] = param_obj.default
                    else:
                        kwargs[param_name] = None
                continue

            # ========== 处理普通参数与带杠选项 ==========
            found, value = _resolve_parsed_value(param_name, parsed_msg_)
            annotation = _unwrap_optional(param_obj.annotation)

            # 选项/标志未提供时解析结果为 False，非 bool 参数应回退到默认值
            if found and value is False and annotation is not bool:
                found = False

            if found:
                try:
                    # 根据类型注解进行类型转换，可选参数按其非 None 类型处理
                    if annotation == int:
                        value = int(value)
                    elif annotation == float:
                        value = float(value)
                    elif annotation == bool:
                        value = bool(value)
                except (TypeError, ValueError):
                    # 类型转换失败，命令格式错误
                    raise InvalidCommandFormatError
                kwargs[param_name] = value
            else:
                # 参数不在解析结果中，使用默认值或 None
                if param_obj.default is not inspect.Parameter.empty:
                    kwargs[param_name] = param_obj.default
                else:
                    kwargs[param_name] = None

        # 警告：函数缺少 MessageSession 参数（可能导致运行时错误）
        if no_message_session:
            Logger.warning(
                f"{command.function.__name__} has no Bot.MessageSession parameter, did you forgot to add it?\n"
                "Remember: MessageSession IS NOT Bot.MessageSession"
            )
    else:
        # 函数只有一个参数，直接传入 MessageSession
        kwargs[func_params[list(func_params.keys())[0]].name] = msg

    return kwargs


async def _execute_module_command(msg: "Bot.MessageSession", module, command_first_word):
    """
    执行模块的命令解析和处理。

    该函数是带命令模板的模块的执行入口，负责：
    1. 使用 CommandParser 解析命令参数
    2. 验证用户权限（超级用户、管理员等）
    3. 检查命令在当前场景中的有效性（平台限制等）
    4. 根据命令函数的参数签名构建调用参数
    5. 显示“正在输入……”状态（如果用户启用）
    6. 执行命令函数

    :param msg: 消息会话对象
    :param module: 模块对象
    :param command_first_word: 命令的第一个词（模块名）
    :return: 仅模板未匹配时返回 False，由外层协调恢复与默认提示。
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
        except InvalidCommandFormatError:
            return False
        command: CommandMeta = parsed_msg[0]
        msg.parsed_msg = parsed_msg[1]  # 使用命令模板解析后的消息
        Logger.trace("Parsed message: " + str(msg.parsed_msg))

        # ========== 步骤 2: 入口 before_execute（权限与平台策略）==========
        authorize_result = await _dispatch_stage(
            HookPoint.COMMAND_BEFORE_EXECUTE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"command": command},
        )
        if isinstance(authorize_result, Stop):
            return

        # ========== 步骤 3: 构建函数参数 ==========
        # 根据命令函数的签名，准备调用参数（含带杠选项到函数参数的映射）
        kwargs = _build_command_kwargs(command, msg, bot)

        # ========== 步骤 4: 显示“正在输入……”状态 ==========
        if msg.session_info.typing_prompt_enabled:
            await msg.start_typing()
            _typing = True

        # ========== 步骤 5: 执行命令函数 ==========
        async with ModuleRuntimeManager.use(module.module_name):
            await parsed_msg[0].function(**kwargs)

        # 如果函数没有使用 msg.finish，手动结束会话
        raise SessionFinished(msg.sent)
    except InvalidCommandFormatError:
        # 模板已匹配后发生的转换错误只进入 hook，不能重新执行命令。
        await _dispatch_stage(
            HookPoint.COMMAND_UNMATCHED,
            msg,
            command_first_word=command_first_word,
            data={"unmatched_kind": "syntax", "suppress_invalid_prompt": module.suppress_invalid_prompt},
        )
    finally:
        if _typing:
            await msg.end_typing()


__all__ = ["parser"]
