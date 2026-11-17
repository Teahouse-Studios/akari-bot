"""会话术语作用域的构造。"""

from __future__ import annotations

import re

from core.i18n import derive_term_candidates

# 场景前缀来自各适配器，形状由平台侧决定；不能进键名或占位符语法的字符一律剔除。
_UNSAFE_TOKEN_CHARS = re.compile(r"[^0-9a-z_]+")


def _normalize_token(part: str) -> str:
    return _UNSAFE_TOKEN_CHARS.sub("", part.strip().lower())


def build_term_candidates(target_from: str | None, is_private: bool) -> tuple[str, ...]:
    """把场景前缀与私聊标志转换为术语候选链。

    :param target_from: 场景前缀，如 ``Discord|DM|Channel``。
    :param is_private: 该会话是否为私聊。
    :return: 候选链，最具体在前；无法解析时返回空元组，由基础术语回落。
    """
    if not target_from:
        return ()
    tokens = tuple(_normalize_token(part) for part in target_from.split("|"))
    if not all(tokens):
        return ()
    try:
        return derive_term_candidates(tokens, shared=("private",) if is_private else ())
    except ValueError:
        # 前缀由平台侧声明，仓库外的适配器可能给出不合规的形状；此时退回基础术语而非中断消息处理。
        return ()
