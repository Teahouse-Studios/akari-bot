"""命令纠错建议：通过 ``parser.command.unmatched`` 返回 RecoveryProposal。"""

from __future__ import annotations

import copy
import re
from typing import TYPE_CHECKING

from rapidfuzz import process

from core.builtins.parser.args import ArgumentPattern, Template as argsTemplate, templates_to_str
from core.builtins.parser.hooks import HookPoint, RecoveryProposal
from core.component import module
from core.config.base import CoreConfig
from core.exports import exports
from core.loader import ModulesManager
from core.logger import Logger
from core.types import Module
from core.types.module.component_meta import CommandMeta

if TYPE_CHECKING:
    from core.builtins.bot import Bot

typo_check_module_score = CoreConfig.typo_check_module_score
typo_check_command_score = CoreConfig.typo_check_command_score
typo_check_args_score = CoreConfig.typo_check_args_score
typo_check_options_score = CoreConfig.typo_check_options_score
typo_check_args_diff_ratio = CoreConfig.typo_check_args_diff_ratio
typo_check_module_diff_ratio = CoreConfig.typo_check_module_diff_ratio

typo = module("typo", hidden=True, load=True, base=True)


def _get_close_matches(word, possibilities, n=1, cutoff=0.6):
    if not 0.0 <= cutoff <= 1.0:
        raise ValueError("cutoff must be between 0.0 and 1.0")
    matches = process.extract(query=word, choices=possibilities, limit=n, score_cutoff=cutoff * 100)
    return [m[0] for m in matches]


def suggest_correction(msg, modules, command_first_word) -> RecoveryProposal | None:
    """计算纠错建议；无建议时返回 None。不做用户确认。"""
    bot = exports["Bot"]
    is_base_superuser = msg.session_info.sender_id in bot.base_superuser_list
    is_superuser = msg.check_super_user()

    available_modules: dict[str, str] = {}
    available_module_targets: dict[str, list[str]] = {}
    for x in modules:
        if modules[x].base or (x in msg.session_info.enabled_modules):
            if modules[x].hidden:
                continue
            if modules[x].required_superuser and not is_superuser:
                continue
            if modules[x].required_base_superuser and not is_base_superuser:
                continue
            if not modules[x].command_list.get(msg.session_info.target_from):
                continue
            available_modules[x] = x
            available_module_targets[x] = [x]
            for alias, target in ModulesManager.modules_aliases.items():
                if target.split(maxsplit=1)[0] == x:
                    alias_first_word = alias.split(maxsplit=1)[0]
                    available_modules.setdefault(alias_first_word, x)
                    available_module_targets.setdefault(alias_first_word, target.split())

    match_close_module = _get_close_matches(command_first_word, list(available_modules), 1, typo_check_module_score)
    if match_close_module:
        input_len = len(command_first_word)
        match_len = len(match_close_module[0])
        if input_len != match_len:
            max_len = max(input_len, match_len)
            min_len = min(input_len, match_len)
            if min_len / max_len < typo_check_module_diff_ratio:
                Logger.debug(
                    f"Module name length difference too large: "
                    f"input='{command_first_word}'({input_len}), match='{match_close_module[0]}'({match_len}), "
                    f"ratio={min_len / max_len:.2f} < {typo_check_module_diff_ratio}"
                )
                match_close_module = []

    if not match_close_module:
        return None

    matched_module_name = match_close_module[0]
    matched_real_module_name = available_modules[matched_module_name]
    matched_module_target = available_module_targets[matched_module_name]
    module_obj: Module = modules[matched_real_module_name]
    Logger.debug(f"Match module: {command_first_word} -> {matched_module_name}")

    none_template = True
    for func in module_obj.command_list.get(msg.session_info.target_from):
        if func.command_template:
            none_template = False
            break

    input_command_split = msg.trigger_msg.split(" ")
    command_split = matched_module_target + input_command_split[1:]
    len_command_split = len(command_split)

    if not none_template and len_command_split > 1:
        get_commands: list[CommandMeta] = module_obj.command_list.get(msg.session_info.target_from)
        command_templates: dict[int, list] = {}
        for func in get_commands:
            command_template: list[argsTemplate] = copy.deepcopy(func.command_template)
            for ct in command_template:
                ct.args_ = [a for a in ct.args if isinstance(a, ArgumentPattern)]
                if (len_args := len(ct.args)) not in command_templates:
                    command_templates[len_args] = [ct]
                else:
                    command_templates[len_args].append(ct)

        max_template_args = max(command_templates.keys())
        if len_command_split - 1 > max_template_args:
            select_templates = command_templates[max_template_args]
        else:
            try:
                select_templates = command_templates[len_command_split - 1]
            except KeyError:
                select_templates = command_templates[
                    min(command_templates.keys(), key=lambda k: abs(k - (len_command_split - 1)))
                ]

        selected_arg_count = len(select_templates[0].args)
        user_arg_count = len_command_split - 1
        max_count = max(user_arg_count, selected_arg_count)
        min_count = min(user_arg_count, selected_arg_count)

        if max_count > 0 and min_count / max_count < typo_check_args_diff_ratio:
            Logger.debug(
                f"Word count difference too large: user={user_arg_count}, template={selected_arg_count}, "
                f"ratio={min_count / max_count:.2f} < {typo_check_args_diff_ratio}"
            )
            match_close_command = []
        else:
            match_close_command = _get_close_matches(
                " ".join(command_split[1:]), templates_to_str(select_templates), 1, typo_check_command_score
            )

        if match_close_command:
            Logger.debug(f"Match command: {' '.join(command_split[1:])} -> {match_close_command[0]}")
            match_split = match_close_command[0]
            m_split_options = filter(None, re.split(r"(\[.*?\])", match_split))
            old_command_split = command_split.copy()
            del old_command_split[0]
            new_command_split = [matched_real_module_name]
            for m_ in m_split_options:
                if m_.startswith("["):
                    m_split = m_.split(" ")
                    if len(m_split) > 1:
                        match_close_options = _get_close_matches(
                            m_split[0][1:], old_command_split, 1, typo_check_options_score
                        )
                        if match_close_options:
                            Logger.debug(f"Match close options: {m_split[0][1:]} -> {match_close_options[0]}")
                            position = old_command_split.index(match_close_options[0])
                            new_command_split.append(m_split[0][1:])
                            new_command_split += old_command_split[position + 1 : position + len(m_split)]
                            del old_command_split[position : position + len(m_split)]
                    else:
                        if m_split[0][1] == "<":
                            if old_command_split:
                                new_command_split.append(old_command_split[0])
                                del old_command_split[0]
                        else:
                            new_command_split.append(m_split[0][1:-1])
                else:
                    m__ = filter(None, m_.split(" "))
                    for mm in m__:
                        if len(old_command_split) > 0:
                            if mm.startswith("<"):
                                new_command_split.append(old_command_split[0])
                                del old_command_split[0]
                            else:
                                match_result = process.extractOne(
                                    old_command_split[0], [mm], score_cutoff=typo_check_args_score * 100
                                )
                                if match_result:
                                    Logger.debug(f"Match close args: {old_command_split[0]} -> {match_result[0]}")
                                    new_command_split.append(mm)
                                    del old_command_split[0]
                                else:
                                    new_command_split.append(old_command_split[0])
                                    del old_command_split[0]
                        else:
                            new_command_split.append(mm)
            new_command_display = " ".join(new_command_split)
            if matched_module_name != matched_real_module_name:
                target_prefix = " ".join(matched_module_target)
                display_suffix = new_command_display[len(target_prefix) :].lstrip()
                new_command_display = matched_module_name + (f" {display_suffix}" if display_suffix else "")
            trigger = " ".join(new_command_split)
            if trigger == msg.trigger_msg and new_command_display == msg.trigger_msg:
                return None
            return RecoveryProposal(
                trigger_msg=trigger,
                command_first_word=matched_real_module_name,
                display=new_command_display,
            )
        if len_command_split - 1 == 1:
            new_command_display = f"{matched_module_name} {' '.join(input_command_split[1:])}"
            trigger = " ".join([matched_real_module_name] + command_split[1:])
            if trigger == msg.trigger_msg:
                return None
            return RecoveryProposal(
                trigger_msg=trigger,
                command_first_word=matched_real_module_name,
                display=new_command_display,
            )
        return None

    new_trigger_msg = matched_real_module_name + (" " + " ".join(command_split[1:]) if len(command_split) > 1 else "")
    if new_trigger_msg == msg.trigger_msg:
        return None
    return RecoveryProposal(
        trigger_msg=new_trigger_msg,
        command_first_word=matched_real_module_name,
        display=new_trigger_msg,
    )


@typo.hook(point=HookPoint.COMMAND_UNMATCHED, priority=50, name="suggest", server_scope=True)
async def _(ctx: "Bot.ParserHookContext"):
    if ctx.data.get("unmatched_kind") != "module" or ctx.data.get("recovery_stale"):
        return None
    if not ctx.msg.session_info.sender_union_info.sender_data.get("typo_check", True):
        return None
    modules = ModulesManager.return_modules_list(
        ctx.msg.session_info.target_from, ctx.msg.session_info.client_name, use_cache=False
    )
    command_first_word = ctx.command_first_word or (ctx.msg.trigger_msg.split(" ", 1)[0] if ctx.msg.trigger_msg else "")
    if not command_first_word:
        return None
    return suggest_correction(ctx.msg, modules, command_first_word)


__all__ = ["typo", "suggest_correction"]
