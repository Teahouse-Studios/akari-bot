"""Parser / 出站入口 hook 公共导出。"""

from .context import OutgoingPayload, ParserHookContext, SessionInfoView
from .dispatch import (
    dispatch_outgoing_before_send,
    dispatch_outgoing_result,
    dispatch_parser_hook,
    get_parser_hook_executor,
    has_hook_subscribers,
    is_outgoing_dispatching,
    reset_parser_hook_executor,
)
from .draft import SessionDraft, SessionDraftError, WRITABLE_FIELDS, build_session_draft
from core.builtins.hooks import DEFAULT_HOOK_TIMEOUT, HookSubscription, build_subscription

from .executor import HookDispatchOutcome, ParserHookExecutor
from .points import ALL_HOOK_POINTS, SESSION_DRAFT_POINTS, HookPoint
from .results import (
    Continue,
    Handled,
    HookResult,
    RecoveryProposal,
    RewriteTrigger,
    Stop,
    StopScope,
    normalize_result,
)

__all__ = [
    "ALL_HOOK_POINTS",
    "Continue",
    "DEFAULT_HOOK_TIMEOUT",
    "Handled",
    "HookDispatchOutcome",
    "HookPoint",
    "HookResult",
    "HookSubscription",
    "OutgoingPayload",
    "ParserHookContext",
    "ParserHookExecutor",
    "RecoveryProposal",
    "RewriteTrigger",
    "SESSION_DRAFT_POINTS",
    "SessionDraft",
    "SessionDraftError",
    "SessionInfoView",
    "Stop",
    "StopScope",
    "WRITABLE_FIELDS",
    "build_session_draft",
    "build_subscription",
    "dispatch_outgoing_before_send",
    "dispatch_outgoing_result",
    "dispatch_parser_hook",
    "get_parser_hook_executor",
    "has_hook_subscribers",
    "is_outgoing_dispatching",
    "normalize_result",
    "reset_parser_hook_executor",
]
