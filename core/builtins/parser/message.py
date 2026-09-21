"""消息解析模块 - 处理消息的完整解析流程。"""

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

LONG_REGEX_MESSAGE_LENGTH = 75

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
    """消息处理的主入口函数。

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

        # 检查是否有等待此消息的任务（如等待用户回复）。入口策略可以明确让出等待路由，
        # 但仍允许消息继续进入普通命令/正则流程。
        wait_result = await _dispatch_stage(HookPoint.SESSION_BEFORE_WAIT, msg)
        if isinstance(wait_result, Stop) and wait_result.scope == StopScope.MESSAGE:
            return
        skip_wait_tasks = isinstance(wait_result, Stop) or (
            isinstance(wait_result, Continue) and wait_result.data.get("skip_wait_tasks", False)
        )
        if not skip_wait_tasks:
            # 独占等待任务或 callback 会消费消息；允许并行路由的等待任务则在完成等待后
            # 继续进入命令/正则路由。
            if await SessionTaskManager.check(msg, allow_wait_fallthrough=True):
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

        if not await _confirm_long_regex_message(msg, modules):
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
    command_parser = CommandParser(
        module, msg=msg, module_name=command_first_word, command_prefixes=msg.session_info.prefixes
    )
    try:
        parsed = command_parser.parse(msg.trigger_msg)
    except InvalidCommandFormatError:
        return False
    return bool(parsed and parsed[0])


def _get_prefixes(msg: "Bot.MessageSession"):
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
    if disable_prefix and not in_prefix_list:
        # 禁用前缀模式，使用完整消息作为命令
        command = msg.trigger_msg
    else:
        # 移除前缀，提取实际命令
        command = msg.trigger_msg[len(msg.session_info.prefixes[0]) :]

    command = command.strip()
    command_split: list = command.split(" ")  # 切割消息为单词列表
    # 别名改写会抹去用户实际输入的首词，退役策略的白名单依赖它
    msg.command_original_word = command_split[0]

    not_alias = False
    cm = ""
    for module_name in modules:
        if command_split[0] == module_name:
            # 找到了匹配的模块，标记为非别名
            not_alias = True
            cm = module_name
            break

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
    time_start = time.perf_counter()
    _typing = False  # 标记是否正在显示“正在输入……”状态
    try:
        module: Module = modules[command_first_word]

        prepare_result = await _dispatch_stage(
            HookPoint.COMMAND_PREPARE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"module": module},
        )
        if isinstance(prepare_result, Stop):
            return

        before_parse_result = await _dispatch_stage(
            HookPoint.COMMAND_BEFORE_PARSE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"base": module.base},
        )
        if isinstance(before_parse_result, Stop):
            return

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
    """判断一个模块的正则处理函数是否应当参与匹配。

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
    """尝试为当前会话获取执行锁。

    :param msg: 消息会话。
    :return: 是否成功获取。
    """
    return await ExecutionLockList.acquire(msg)


def regex_func_available(rfunc, target_from: str, client_name: str) -> bool:
    """判断一条正则处理函数在当前平台上是否可用。

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


def _match_regex(rfunc, trigger_msg: str):
    if rfunc.mode in ("M", "MATCH"):
        matched_msg = rfunc.compiled.match(trigger_msg)
        return bool(matched_msg), matched_msg
    if rfunc.mode in ("A", "FINDALL"):
        matched_msg = tuple(set(rfunc.compiled.findall(trigger_msg)))
        return bool(matched_msg), matched_msg
    return False, None


def _regex_module_available(msg: "Bot.MessageSession", module: Module, module_name: str) -> bool:
    if not regex_module_enabled(
        module, module_name, msg.session_info.enabled_modules, msg.session_info.read_all_messages
    ):
        return False
    if not module.load:
        return False
    if msg.session_info.target_from in module.exclude_from or msg.session_info.client_name in module.exclude_from:
        return False
    return (
        "*" in module.available_for
        or msg.session_info.target_from in module.available_for
        or msg.session_info.client_name in module.available_for
    )


def _regex_matches_message(msg: "Bot.MessageSession", modules) -> bool:
    if len(msg.trigger_msg) <= LONG_REGEX_MESSAGE_LENGTH:
        return False

    for module_name, module in modules.items():
        if not module._db_load or not module.regex_list.set or not _regex_module_available(msg, module, module_name):
            continue
        for index, rfunc in enumerate(module.regex_list.set):
            if not regex_func_available(rfunc, msg.session_info.target_from, msg.session_info.client_name):
                continue
            if rfunc.trigger_once_startup and regex_once_triggered(module_name, index, msg.session_info.target_id):
                continue
            trigger_msg = msg.as_display(text_only=rfunc.text_only, element_filter=rfunc.element_filter)
            try:
                matched, _ = _match_regex(rfunc, trigger_msg)
            except Exception:
                continue
            if matched and not getattr(rfunc, "skip_long_message_confirm", False):
                return True
    return False


async def _confirm_long_regex_message(msg: "Bot.MessageSession", modules) -> bool:
    if not _regex_matches_message(msg, modules):
        return True
    return await msg.wait_confirm(I18NContext("parser.regex.message_too_long"), consume_any_message=True)


async def _execute_regex(msg: "Bot.MessageSession", modules, identify_str):
    # 同一条消息会被所有模块的正则轮流匹配，而渲染结果只由这两个参数决定，
    # 按参数缓存一次，避免每条正则都把消息链重新走一遍
    display_cache: dict[tuple[bool, tuple], str] = {}

    def get_trigger_msg(text_only: bool, element_filter) -> str:
        cache_key = (text_only, tuple(element_filter or ()))
        if cache_key not in display_cache:
            display_cache[cache_key] = msg.as_display(text_only=text_only, element_filter=element_filter)
        return display_cache[cache_key]

    for m in modules:
        # 跳过未加载的模块
        if not modules[m]._db_load:
            continue

        try:
            if (
                regex_module_enabled(
                    modules[m], m, msg.session_info.enabled_modules, msg.session_info.read_all_messages
                )
                and modules[m].regex_list.set
            ):
                regex_module: Module = modules[m]

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

                        matched, msg.matched_msg = _match_regex(rfunc, trigger_msg)
                        if matched:
                            matched_hash = hash(
                                msg.matched_msg.groups() if rfunc.mode in ("M", "MATCH") else msg.matched_msg
                            )

                        if matched:
                            if rfunc.logging:
                                Logger.info(f"{identify_str} -> [Bot]: {msg.trigger_msg}")
                            Logger.debug("Matched hash:" + str(matched_hash))

                            if rfunc.logging and matched_hash in match_hash_cache[msg.session_info.target_id]:
                                Logger.warning("Match loop detected, skipping...")
                                continue

                            match_hash_cache[msg.session_info.target_id][matched_hash] = ExpiringTempDict(
                                exp=1, root=False
                            )

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
                                    await rfunc.function(msg)

                            else:
                                async with ModuleRuntimeManager.use(regex_module.module_name):
                                    await rfunc.function(msg)
                            ExecutionLockList.remove(msg)
                            raise SessionFinished(msg.sent)
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
    return inspect.signature(func)


def _unwrap_optional(annotation):
    if get_origin(annotation) in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _unwrap_option_value(value):
    if isinstance(value, dict) and len(value) == 1:
        return next(iter(value.values()))
    return value


def _resolve_parsed_value(param_name: str, parsed_msg: dict):
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
    kwargs = {}
    func_params = _get_cached_signature(command.function).parameters

    if len(func_params) > 1 and msg.parsed_msg:
        parsed_msg_ = msg.parsed_msg
        no_message_session = True

        for param_name, param_obj in func_params.items():
            if param_obj.annotation == bot.MessageSession:
                kwargs[param_name] = msg
                no_message_session = False
                continue

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
                    if param_obj.default is not inspect.Parameter.empty:
                        kwargs[param_name] = param_obj.default
                    else:
                        kwargs[param_name] = None
                continue

            found, value = _resolve_parsed_value(param_name, parsed_msg_)
            annotation = _unwrap_optional(param_obj.annotation)

            # 选项/标志未提供时解析结果为 False，非 bool 参数应回退到默认值
            if found and value is False and annotation is not bool:
                found = False

            if found:
                try:
                    if annotation == int:
                        value = int(value)
                    elif annotation == float:
                        value = float(value)
                    elif annotation == bool:
                        value = bool(value)
                except (TypeError, ValueError):
                    raise InvalidCommandFormatError
                kwargs[param_name] = value
            else:
                if param_obj.default is not inspect.Parameter.empty:
                    kwargs[param_name] = param_obj.default
                else:
                    kwargs[param_name] = None

        if no_message_session:
            Logger.warning(
                f"{command.function.__name__} has no Bot.MessageSession parameter, did you forgot to add it?\n"
                "Remember: MessageSession IS NOT Bot.MessageSession"
            )
    else:
        kwargs[func_params[list(func_params.keys())[0]].name] = msg

    return kwargs


async def _execute_module_command(msg: "Bot.MessageSession", module, command_first_word):
    bot: "Bot" = exports["Bot"]
    _typing = False
    try:
        command_parser = CommandParser(
            module, msg=msg, module_name=command_first_word, command_prefixes=msg.session_info.prefixes
        )
        try:
            parsed_msg = command_parser.parse(msg.trigger_msg)
        except InvalidCommandFormatError:
            return False
        command: CommandMeta = parsed_msg[0]
        msg.parsed_msg = parsed_msg[1]
        Logger.trace("Parsed message: " + str(msg.parsed_msg))

        authorize_result = await _dispatch_stage(
            HookPoint.COMMAND_BEFORE_EXECUTE,
            msg,
            module_name=command_first_word,
            command_first_word=command_first_word,
            data={"command": command},
        )
        if isinstance(authorize_result, Stop):
            return

        kwargs = _build_command_kwargs(command, msg, bot)

        if msg.session_info.typing_prompt_enabled:
            await msg.start_typing()
            _typing = True

        async with ModuleRuntimeManager.use(module.module_name):
            await parsed_msg[0].function(**kwargs)

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
