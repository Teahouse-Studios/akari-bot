"""random choice 的 AI 选择流程。"""

import re
from pathlib import Path
from string import Template

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.constants.path import module_data_path
from core.i18n import Locale, get_available_locales
from core.logger import Logger

HOOK_NAME = "ai.ask"
STATUS_OK = "ok"
STATUS_NOT_ENOUGH_PETAL = "not_enough_petal"
REFUSAL_KEY = "random.message.choice.refused"
LEADING_INDEX_PATTERN = re.compile(r"^\s*\d+\s*[.、)）．:：]\s*")
UNTRANSLATED_MARK = "{I18N:"


def _load_prompt(filename: str) -> str:
    path = module_data_path(Path(__file__).parent) / filename
    if not path.exists():
        Logger.warning(f"Prompt file {path} not found.")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


CHOICE_INSTRUCTIONS = _load_prompt("choice_instructions.txt")
CHOICE_PROMPT = _load_prompt("choice_prompt.txt")


def _localized_refusal(locale: Locale) -> str:
    text = locale.t(REFUSAL_KEY, locale_failed_prompt=False).strip()
    return "" if UNTRANSLATED_MARK in text else text


def build_choice_prompt(choices: list[str]) -> str:
    """把候选元素填入用户提示词模板。

    :param choices: 候选元素。
    :return: 交给模型的用户输入。
    """
    candidates = "\n".join(f"{index}. {choice}" for index, choice in enumerate(choices, start=1))
    return Template(CHOICE_PROMPT).safe_substitute(candidates=candidates)


def build_instructions(refusal: str) -> str:
    """把当前会话语言的拒答语句填入提示词。

    :param refusal: 当前会话语言的拒答语句。
    :return: 交给模型的附加系统提示。
    """
    return Template(CHOICE_INSTRUCTIONS).safe_substitute(refusal=refusal)


def get_refusal_texts(locale: Locale) -> set[str]:
    """取出各语言本地化文件中的拒答语句，用于识别模型的规避输出。

    :param locale: 调用方所在会话的本地化对象，其语言优先。
    :return: 各语言的拒答语句集合。
    """
    texts = {_localized_refusal(locale)}
    for language in get_available_locales():
        texts.add(_localized_refusal(Locale(language)))
    texts.discard("")
    return texts


def match_choice(text: str, choices: list[str]) -> str | None:
    """将模型输出还原为原始候选元素。

    输出始终取自候选元素本身：模型带上序号或前后缀时按元素原文回填，
    无法唯一确定属于哪个候选时返回 None。

    :param text: 模型输出。
    :param choices: 候选元素。
    :return: 匹配到的候选元素；不匹配或存在歧义时返回 None。
    """
    if text in choices:
        return text
    stripped = LEADING_INDEX_PATTERN.sub("", text)
    if stripped in choices:
        return stripped

    matched = {candidate for candidate in choices if candidate and candidate in text}
    # 候选之间互为子串时保留更长的那个，避免把「app」与「apple」误判为歧义
    matched = {candidate for candidate in matched if not any(candidate in other for other in matched - {candidate})}
    if len(matched) == 1:
        return matched.pop()
    return None


async def ask_ai_choice(msg: Bot.MessageSession, choices: list[str]) -> list | None:
    """请求 ai 模块在候选元素中完成选择。

    :param msg: 消息会话。
    :param choices: 候选元素。
    :return: 可直接发送的消息元素列表；hook 不可用或调用失败时返回 None，由调用方回退到本地实现。
    """
    if not CHOICE_INSTRUCTIONS or not CHOICE_PROMPT:
        Logger.warning("Choice prompt files are missing, skip AI choice.")
        return None
    refusal = _localized_refusal(msg.session_info.locale)
    if not refusal:
        Logger.warning(f"Localized text for {REFUSAL_KEY} not found, skip AI choice.")
        return None

    try:
        result = await Bot.Hook.trigger(
            HOOK_NAME,
            session_info=msg.session_info,
            args={
                "prompt": build_choice_prompt(choices),
                "instructions": build_instructions(refusal),
                "use_tools": False,
            },
            timeout=0,
        )
        if result is None:
            return None
        if result.status == STATUS_NOT_ENOUGH_PETAL:
            await msg.finish(I18NContext("petal.message.cost.not_enough"))
        if result.status != STATUS_OK:
            Logger.debug(f"{HOOK_NAME} hook unavailable ({result.status}), fallback to local random.")
            return None

        text = (result.text or "").strip()
        if not text or any(refusal_text in text for refusal_text in get_refusal_texts(msg.session_info.locale)):
            await msg.finish(I18NContext(REFUSAL_KEY))
        answer = match_choice(text, choices)
        if answer is None:
            # 模型输出元素以外的内容时同样拒答，避免回显候选之外的内容
            Logger.debug(f"Unmatched AI choice reply: {text!r}.")
            await msg.finish(I18NContext(REFUSAL_KEY))

        chain = [Plain(answer)]
        if result.petal > 0:
            chain.append(I18NContext("petal.message.cost", amount=result.petal))
        return chain
    except ValueError:
        # ai 模块未加载或未注册 ai.ask，直接回退
        return None
    except Exception:
        Logger.exception(f"{HOOK_NAME} hook failed, fallback to local random: ")
        return None


__all__ = [
    "ask_ai_choice",
    "build_choice_prompt",
    "build_instructions",
    "get_refusal_texts",
    "match_choice",
]
