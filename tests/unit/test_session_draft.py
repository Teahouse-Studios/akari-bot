"""SessionDraft 与出站入口单元测试。"""

from types import SimpleNamespace

from core.builtins.parser.hooks import (
    Continue,
    HookPoint,
    OutgoingPayload,
    ParserHookExecutor,
    SessionDraft,
    SessionDraftError,
    SessionInfoView,
    Stop,
    StopScope,
    build_session_draft,
    build_subscription,
)
from core.tester import Tester, func_case
from core.types import Module
from core.types.module.component_meta import HookMeta


class _FakeLocale:
    lang = "zh_cn"


class _FakeInfo:
    def __init__(self):
        self.tmp = {"a": "1"}
        self.prefixes = ["~"]
        self.messages = None
        self.bot_name = "Bot"
        self.muted = False
        self.locale = _FakeLocale()
        self.target_from = "TEST|t"
        self.client_name = "TEST"
        self.sender_id = "TEST|1"
        self.target_id = "TEST|2"


class _FakeMsg:
    def __init__(self):
        self.session_info = _FakeInfo()
        self.trigger_msg = "ping"
        self.sent = []


def _make_module(name: str) -> Module:
    m = Module.assign(module_name=name, alias=None, recommend_modules=None, developers=None)
    m._db_load = True
    m.load = True
    return m


def _test_draft_isolation_and_commit():
    try:
        msg = _FakeMsg()
        draft = build_session_draft(msg.session_info)
        draft.set_tmp("b", "2")
        draft.prefixes = ["!", "~"]
        assert msg.session_info.tmp == {"a": "1"}
        assert msg.session_info.prefixes == ["~"]
        draft.commit()
        assert msg.session_info.tmp["b"] == "2"
        assert msg.session_info.prefixes[0] == "!"
        draft._tmp["c"] = "3"
        assert "c" not in msg.session_info.tmp
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_draft_failure_discard():
    try:
        msg = _FakeMsg()

        async def h1(ctx):
            ctx.draft.set_tmp("from_h1", "1")
            return Continue()

        async def h2(ctx):
            ctx.draft.set_tmp("from_h2", "1")
            raise RuntimeError("boom")

        async def h3(ctx):
            return Continue()

        mm = SimpleNamespace(
            modules={n: _make_module(n) for n in ("a", "b", "c")},
            parser_hook_subscriptions={
                HookPoint.COMMAND_PREPARE: [
                    build_subscription("a", HookMeta(function=h1, point=HookPoint.COMMAND_PREPARE, name="1"), 0),
                    build_subscription("b", HookMeta(function=h2, point=HookPoint.COMMAND_PREPARE, name="2"), 0),
                    build_subscription("c", HookMeta(function=h3, point=HookPoint.COMMAND_PREPARE, name="3"), 0),
                ]
            },
        )
        await ParserHookExecutor(mm).dispatch(HookPoint.COMMAND_PREPARE, msg)
        assert msg.session_info.tmp.get("from_h1") == "1"
        assert "from_h2" not in msg.session_info.tmp
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_outgoing_before_send_modifies_and_stops():
    try:
        msg = _FakeMsg()
        calls = []

        async def rewrite(ctx):
            calls.append("rewrite")
            ctx.outgoing.chain = "rewritten"
            return Continue()

        async def block(ctx):
            calls.append("block")
            return Stop(scope=StopScope.MESSAGE)

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.OUTGOING_BEFORE_SEND: [
                    build_subscription(
                        "a", HookMeta(function=rewrite, point=HookPoint.OUTGOING_BEFORE_SEND, name="r"), 0
                    ),
                ]
            },
        )
        payload = OutgoingPayload(chain="original", quote=True)
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.OUTGOING_BEFORE_SEND, msg, outgoing=payload)
        assert payload.chain == "rewritten"
        assert isinstance(outcome.result, Continue)

        mm.parser_hook_subscriptions[HookPoint.OUTGOING_BEFORE_SEND] = [
            build_subscription("b", HookMeta(function=block, point=HookPoint.OUTGOING_BEFORE_SEND, name="b"), 0)
        ]
        payload2 = OutgoingPayload(chain="original")
        outcome2 = await ParserHookExecutor(mm).dispatch(HookPoint.OUTGOING_BEFORE_SEND, msg, outgoing=payload2)
        assert isinstance(outcome2.result, Stop)
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


def _test_draft_rejects_double_commit():
    try:
        msg = _FakeMsg()
        draft = SessionDraft(msg.session_info)
        draft.commit()
        try:
            draft.commit()
            return False
        except SessionDraftError:
            pass
        draft2 = SessionDraft(msg.session_info)
        draft2.revoke()
        try:
            draft2.commit()
            return False
        except SessionDraftError:
            return True
    except Exception:
        return False


def _test_commit_only_dirty_fields():
    try:
        msg = _FakeMsg()
        msg.session_info.prefixes = ["~"]
        draft = SessionDraft(msg.session_info)
        draft.set_tmp("k", "v")
        draft.commit()
        assert msg.session_info.tmp["k"] == "v"
        assert msg.session_info.prefixes == ["~"]
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


def _test_draft_session_info_readonly():
    try:
        from core.builtins.parser.hooks import SessionInfoView

        msg = _FakeMsg()
        draft = SessionDraft(msg.session_info)
        view = draft.session_info
        assert isinstance(view, SessionInfoView)
        try:
            view.tmp = {}
            return False
        except AttributeError:
            return True
    except Exception:
        return False


@func_case
async def test_session_draft_outgoing(tester: Tester):
    await tester.test(_test_draft_isolation_and_commit, "draft isolation and commit")
    await tester.test(_test_draft_failure_discard, "draft failure discard")
    await tester.test(_test_outgoing_before_send_modifies_and_stops, "outgoing before_send")
    await tester.test(_test_draft_rejects_double_commit, "draft double commit rejected")
    await tester.test(_test_commit_only_dirty_fields, "commit only dirty fields")
    await tester.test(_test_draft_session_info_readonly, "draft session_info readonly")
    await tester.test(_test_readonly_containers_detached, "readonly session containers detached")
    await tester.test(_test_readonly_union_methods_hidden, "readonly Union methods hidden")
    await tester.test(_test_readonly_message_copy_failure, "readonly message copy failure cannot expose source")
    await tester.test(_test_draft_locale_requires_nonempty_string, "draft locale rejects missing or empty language")
    await tester.test(_test_outgoing_message_nodes_isolated, "outgoing MessageNodes isolated")
    await tester.test(_test_apply_from_detaches_draft_reference, "apply_from detaches draft reference")
    await tester.test(_test_draft_messages_type_validated, "draft messages type validated")


def _test_readonly_containers_detached():
    info = _FakeInfo()
    info.enabled_modules = ["safe"]
    info.next_hops = ["TEST|next"]
    info.platform_prefixes = ["/"]
    info.extra_data = {"nested": [{"items": ["original"]}]}
    info.tmp = {"nested": ["original"]}
    view = SessionInfoView(info)
    view.enabled_modules.append("injected")
    view.next_hops.clear()
    view.platform_prefixes.clear()
    view.extra_data["nested"][0]["items"].append("injected")
    view.tmp["nested"].clear()
    assert info.enabled_modules == ["safe"]
    assert info.next_hops == ["TEST|next"]
    assert info.platform_prefixes == ["/"]
    assert info.extra_data == {"nested": [{"items": ["original"]}]}
    assert info.tmp == {"nested": ["original"]}
    return True


def _test_readonly_union_methods_hidden():
    from core.builtins.session.info import SessionInfo
    from core.database.models import SenderUnionInfo, TargetUnionBind, TargetUnionInfo

    sender = SenderUnionInfo(union_id="readonly-sender", sender_data={"nested": ["original"]})
    target = TargetUnionInfo(union_id="readonly-target", modules=["safe"], target_data={"nested": ["original"]})
    target.bind = TargetUnionBind(target_id="TEST|target", union_id=target.union_id)
    info = SessionInfo(
        target_id="TEST|target",
        target_from="TEST",
        client_name="TEST",
        sender_union_info=sender,
        target_union_info=target,
    )
    view = SessionInfoView(info)
    sender_view = view.sender_union_info
    target_view = view.target_union_info
    for obj, methods in (
        (view, ("refresh_info", "assign")),
        (sender_view, ("edit_attr", "save", "delete", "switch_identity", "warn_user")),
        (target_view, ("edit_attr", "save", "delete", "merge_union")),
        (target_view.bind, ("save", "delete")),
    ):
        for method in methods:
            assert not hasattr(obj, method), method
    extra = SessionInfoView(SimpleNamespace(tmp={}, prefixes=[], future_write=lambda: None))
    assert not hasattr(extra, "future_write")
    assert sender_view.union_id == sender.union_id
    assert target_view.bind.target_id == "TEST|target"
    sender_view.sender_data["nested"].clear()
    target_view.target_data["nested"].clear()
    target_view.modules.append("injected")
    assert sender.sender_data == {"nested": ["original"]}
    assert target.target_data == {"nested": ["original"]}
    assert target.modules == ["safe"]
    assert view.locale.locale == info.locale.locale
    assert view.locale is not info.locale
    return True


def _test_readonly_message_copy_failure():
    from core.builtins.message.chain import MessageChain

    class UncopyableChain(MessageChain):
        def __deepcopy__(self, memo):
            raise RuntimeError("cannot clone message")

    info = _FakeInfo()
    info.messages = UncopyableChain(values=[])
    view = SessionInfoView(info)
    try:
        view.messages
    except RuntimeError as exc:
        assert str(exc) == "cannot clone message"
        return True
    return False


def _test_draft_locale_requires_nonempty_string():
    msg = _FakeMsg()
    original_locale = msg.session_info.locale
    draft = SessionDraft(msg.session_info)
    for invalid in (None, "", " \t\n", 123):
        try:
            draft.locale_lang = invalid
        except SessionDraftError:
            pass
        else:
            return False
        assert "locale_lang" not in draft.dirty_fields
        assert draft.locale_lang == "zh_cn"
        assert msg.session_info.locale is original_locale
    draft.locale_lang = "en_us"
    draft.commit()
    assert msg.session_info.locale.locale == "en_us"

    # 缺省语言仍可读取为 None，修改其它字段不要求补写语言。
    msg.session_info.locale = None
    untouched_locale = SessionDraft(msg.session_info)
    assert untouched_locale.locale_lang is None
    untouched_locale.set_tmp("valid", "1")
    untouched_locale.commit()
    assert msg.session_info.locale is None
    assert msg.session_info.tmp["valid"] == "1"
    return True


async def _test_outgoing_message_nodes_isolated():
    try:
        from core.builtins.message.chain import MessageChain, MessageNodes

        async def mutator(ctx):
            ctx.outgoing.chain.values[0].values[0].text = "failed mutation"
            raise RuntimeError("boom")

        mm = SimpleNamespace(
            modules={"a": _make_module("a")},
            parser_hook_subscriptions={
                HookPoint.OUTGOING_BEFORE_SEND: [
                    build_subscription(
                        "a", HookMeta(function=mutator, point=HookPoint.OUTGOING_BEFORE_SEND, name="m"), 0
                    )
                ]
            },
        )
        original = OutgoingPayload(chain=MessageNodes.assign([MessageChain.assign("original safe")]))
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.OUTGOING_BEFORE_SEND, _FakeMsg(), outgoing=original)
        assert outcome.failed == 1
        # 正式 payload 的节点文本未被失败 hook 改写
        assert original.chain.values[0].values[0].text == "original safe"
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_apply_from_detaches_draft_reference():
    try:
        from core.builtins.message.chain import MessageChain

        held = {}

        async def h1(ctx):
            ctx.outgoing.chain.values[0].text = "h1 rewrite"
            held["draft"] = ctx.outgoing.chain
            return Continue()

        async def h2(ctx):
            # h2 修改 h1 保留的草稿链，然后失败
            held["draft"].values[0].text = "late mutation of prior draft"
            raise RuntimeError("boom")

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.OUTGOING_BEFORE_SEND: [
                    build_subscription("a", HookMeta(function=h1, point=HookPoint.OUTGOING_BEFORE_SEND, name="1"), 0),
                    build_subscription("b", HookMeta(function=h2, point=HookPoint.OUTGOING_BEFORE_SEND, name="2"), 0),
                ]
            },
        )
        payload = OutgoingPayload(chain=MessageChain.assign("original"))
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.OUTGOING_BEFORE_SEND, _FakeMsg(), outgoing=payload)
        assert outcome.failed == 1
        # h1 的改写已提交，但 h2 对保留草稿的污染没有进入正式结果
        assert payload.chain.values[0].text == "h1 rewrite"
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


def _test_draft_messages_type_validated():
    try:
        msg = _FakeMsg()
        draft = SessionDraft(msg.session_info)
        try:
            draft.messages = {"not": "a chain"}
            return False
        except SessionDraftError:
            pass
        assert msg.session_info.messages is None
        # MessageChain 可以正常提交
        from core.builtins.message.chain import MessageChain

        draft2 = SessionDraft(msg.session_info)
        draft2.messages = MessageChain.assign("ok")
        draft2.commit()
        assert msg.session_info.messages is not None
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False
