"""parser 入口 hook 执行器与注册索引单元测试。"""

from types import SimpleNamespace

from core.builtins.parser.hooks import (
    Continue,
    HookPoint,
    HookSubscription,
    ParserHookExecutor,
    Stop,
    StopScope,
    build_subscription,
    normalize_result,
)
from core.builtins.hooks import platform_allows, subscription_sort_key
from core.builtins.parser.hooks.dispatch import reset_parser_hook_executor
from core.builtins.parser.hooks.dispatch import get_parser_hook_executor
from core.loader import ModulesManager
from core.tester import func_case, Tester
from core.types import Module
from core.types.module.component_meta import HookMeta


class _FakeMsg:
    def __init__(self):
        self.session_info = SimpleNamespace(
            target_from="TEST|target",
            client_name="TEST",
            target_id="TEST|1",
            sender_id="TEST|2",
            target_union_id=None,
            sender_union_id=None,
            tmp={},
            prefixes=["~"],
            messages=None,
            bot_name="Bot",
            muted=False,
            locale=None,
            enabled_modules=[],
            require_enable_modules=False,
        )
        self.trigger_msg = "ping"
        self.sent = []
        self.check_super_user = lambda: False


def _make_module(name: str, *, db_load: bool = True, load: bool = True) -> Module:
    module = Module.assign(module_name=name, alias=None, recommend_modules=None, developers=None)
    module._db_load = db_load
    module.load = load
    return module


def _test_normalize_result():
    try:
        assert isinstance(normalize_result(None), Continue)
        stop = Stop(scope=StopScope.MESSAGE)
        assert normalize_result(stop) is stop
        try:
            normalize_result({"truthy": True})
            return False
        except TypeError:
            return True
    except Exception:
        return False


def _test_subscription_sort_and_platform():
    try:
        a = build_subscription(
            "mod_a",
            HookMeta(function=lambda ctx: None, point=HookPoint.COMMAND_PREPARE, priority=10, name="a"),
            0,
        )
        b = build_subscription(
            "mod_b",
            HookMeta(function=lambda ctx: None, point=HookPoint.COMMAND_PREPARE, priority=10, name="b"),
            0,
        )
        assert subscription_sort_key(a) < subscription_sort_key(b)

        limited = build_subscription(
            "mod_c",
            HookMeta(
                function=lambda ctx: None,
                point=HookPoint.COMMAND_PREPARE,
                available_for=["QQ"],
                exclude_from=[],
                name="c",
            ),
            0,
        )
        assert not platform_allows(limited.available_for, limited.exclude_from, "TEST|1", "TEST")
        assert platform_allows(limited.available_for, limited.exclude_from, "QQ|1", "QQ")
        assert platform_allows(a.available_for, a.exclude_from, "TEST|1", "TEST")
        return True
    except Exception:
        return False


async def _test_executor_isolates_failures():
    try:
        called = []

        async def ok(ctx):
            called.append("ok")
            return Continue()

        async def boom(ctx):
            called.append("boom")
            raise RuntimeError("hook failed")

        async def reject(ctx):
            called.append("reject")
            return Stop(scope=StopScope.MESSAGE)

        async def later(ctx):
            called.append("later")
            return Continue()

        mm = SimpleNamespace(modules={}, parser_hook_subscriptions={})
        mm.modules["m1"] = _make_module("m1")
        mm.modules["m2"] = _make_module("m2")
        mm.modules["m3"] = _make_module("m3")
        mm.modules["m4"] = _make_module("m4")
        subs = [
            build_subscription("m1", HookMeta(function=ok, point=HookPoint.COMMAND_PREPARE, priority=10), 0),
            build_subscription("m2", HookMeta(function=boom, point=HookPoint.COMMAND_PREPARE, priority=20), 0),
            build_subscription("m3", HookMeta(function=reject, point=HookPoint.COMMAND_PREPARE, priority=30), 0),
            build_subscription("m4", HookMeta(function=later, point=HookPoint.COMMAND_PREPARE, priority=40), 0),
        ]
        mm.parser_hook_subscriptions = {HookPoint.COMMAND_PREPARE: subs}

        executor = ParserHookExecutor(mm)
        outcome = await executor.dispatch(HookPoint.COMMAND_PREPARE, _FakeMsg())
        assert called == ["ok", "boom", "reject"]
        assert isinstance(outcome.result, Stop)
        assert outcome.executed == 2
        assert outcome.failed == 1
        return True
    except Exception:
        return False


async def _test_executor_skips_disabled_module_fixed():
    try:
        called_modules = []

        async def hook(ctx):
            called_modules.append(True)
            return Continue()

        mm = SimpleNamespace(modules={}, parser_hook_subscriptions={})
        mm.modules["off"] = _make_module("off", db_load=False)
        mm.modules["on"] = _make_module("on")
        mm.parser_hook_subscriptions = {
            HookPoint.FINISHED: [
                build_subscription("off", HookMeta(function=hook, point=HookPoint.FINISHED, name="a"), 0),
                build_subscription("on", HookMeta(function=hook, point=HookPoint.FINISHED, name="b"), 0),
            ]
        }
        executor = ParserHookExecutor(mm)
        await executor.dispatch(HookPoint.FINISHED, _FakeMsg())
        return called_modules == [True]
    except Exception:
        return False


async def _test_loader_indexes_point_hooks():
    try:
        reset_parser_hook_executor()
        module_name = "__test_parser_hooks_mod"
        module = _make_module(module_name)

        async def named(ctx):
            return None

        async def pointed(ctx):
            return Continue()

        module.hooks_list.add(HookMeta(function=named, name="reload"))
        module.hooks_list.add(HookMeta(function=pointed, point=str(HookPoint.COMMAND_PREPARE), priority=5, name="p"))
        ModulesManager.modules[module_name] = module
        try:
            ModulesManager.refresh_modules_hooks()
            assert ModulesManager.modules_hooks.get(f"{module_name}.reload") is named
            assert ModulesManager.modules_hook_subscriptions[f"{module_name}.reload"][0].function is named
            assert ModulesManager.module_hook_subscriptions[module_name][0].function is named
            subs = ModulesManager.parser_hook_subscriptions.get(HookPoint.COMMAND_PREPARE) or []
            assert any(s.subscription_id.endswith(":p") and s.module_name == module_name for s in subs)
            # 确保 named hook 未进入 point 索引
            assert all(s.meta.name != "reload" for s in subs)
            return True
        finally:
            ModulesManager.modules.pop(module_name, None)
            ModulesManager.refresh_modules_hooks()
            reset_parser_hook_executor()
    except Exception:
        return False


async def _test_invalid_result_isolated():
    try:
        seen = []

        async def bad(ctx):
            return {"nope": True}

        async def good(ctx):
            seen.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.EXECUTION_FINISHED: [
                    build_subscription("a", HookMeta(function=bad, point=HookPoint.EXECUTION_FINISHED, name="bad"), 0),
                    build_subscription(
                        "b", HookMeta(function=good, point=HookPoint.EXECUTION_FINISHED, name="good"), 0
                    ),
                ]
            },
        )
        executor = ParserHookExecutor(mm)
        outcome = await executor.dispatch(HookPoint.EXECUTION_FINISHED, _FakeMsg())
        assert seen == [1]
        assert isinstance(outcome.result, Continue)
        assert outcome.failed == 1
        return True
    except Exception:
        return False


async def _test_protocol_exception_isolated():
    try:
        from core.constants.exceptions import SessionFinished

        called = []

        async def raise_sf(ctx):
            raise SessionFinished("nope")

        async def after(ctx):
            called.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.COMMAND_PREPARE: [
                    build_subscription("a", HookMeta(function=raise_sf, point=HookPoint.COMMAND_PREPARE, name="sf"), 0),
                    build_subscription("b", HookMeta(function=after, point=HookPoint.COMMAND_PREPARE, name="after"), 0),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.COMMAND_PREPARE, _FakeMsg())
        assert called == [1]
        assert outcome.failed == 1
        assert isinstance(outcome.result, Continue)
        return True
    except Exception:
        return False


async def _test_timeout_discards_result():
    try:
        import asyncio

        called = []

        async def slow(ctx):
            await asyncio.sleep(0.05)
            called.append("slow")
            return Stop(scope=StopScope.MESSAGE)

        async def after(ctx):
            called.append("after")
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.FINISHED: [
                    build_subscription("a", HookMeta(function=slow, point=HookPoint.FINISHED, name="slow"), 0),
                    build_subscription("b", HookMeta(function=after, point=HookPoint.FINISHED, name="after"), 0),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg(), timeout=0.01)
        # after 仍应执行；slow 的 Stop 不被采纳
        assert "after" in called
        assert isinstance(outcome.result, Continue)
        return True
    except Exception:
        return False


async def _test_handled_short_circuits():
    try:
        from core.builtins.parser.hooks import Handled

        called = []

        async def handle(ctx):
            called.append("handle")
            return Handled()

        async def later(ctx):
            called.append("later")
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.EXECUTION_ERROR: [
                    build_subscription("a", HookMeta(function=handle, point=HookPoint.EXECUTION_ERROR, name="h"), 0),
                    build_subscription("b", HookMeta(function=later, point=HookPoint.EXECUTION_ERROR, name="l"), 0),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.EXECUTION_ERROR, _FakeMsg())
        assert called == ["handle"]
        assert isinstance(outcome.result, Handled)
        return True
    except Exception:
        return False


async def _test_typo_suggests_close_module():
    try:
        from core.builtins.parser.hooks import RecoveryProposal
        from modules.core.hooks.typo import suggest_correction

        class _CmdList:
            def __init__(self, cmds):
                self.set = cmds

            def get(self, *a, **k):
                return self.set

        class _Func:
            command_template = []

        class _Mod:
            base = True
            hidden = False
            required_superuser = False
            required_base_superuser = False
            command_list = _CmdList([_Func()])

        msg = _FakeMsg()
        msg.trigger_msg = "zztestwik"
        msg.session_info.sender_id = "TEST|typo_user"
        msg.session_info.sender_union_info = SimpleNamespace(sender_data={})
        msg.session_info.enabled_modules = []
        msg.session_info.target_from = "TEST|target"
        msg.session_info.client_name = "TEST"
        msg.check_super_user = lambda: False

        from core.exports import exports

        class _Bot:
            base_superuser_list = []

        saved = exports.get("Bot")
        exports["Bot"] = _Bot()
        try:
            modules = {"zztestwiki": _Mod()}
            proposal = suggest_correction(msg, modules, "zztestwik")
        finally:
            if saved is not None:
                exports["Bot"] = saved
        return isinstance(proposal, RecoveryProposal) and proposal.command_first_word == "zztestwiki"
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_stale_generation_skipped():
    try:
        from core.module_runtime import ModuleRuntimeManager

        called = []

        async def hook(ctx):
            called.append(1)
            return Continue()

        module_name = "gen_mod_test"
        ModuleRuntimeManager.get_or_create(module_name)
        current_gen = ModuleRuntimeManager._current[module_name].generation

        stale = build_subscription(
            module_name,
            HookMeta(function=hook, point=HookPoint.FINISHED, name="stale"),
            0,
        )
        # 构造代际不一致的订阅
        object.__setattr__(  # frozen dataclass
            stale,
            "generation",
            current_gen + 99,
        )

        mm = SimpleNamespace(
            modules={module_name: _make_module(module_name)},
            parser_hook_subscriptions={HookPoint.FINISHED: [stale]},
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg())
        assert called == []
        assert outcome.skipped_stale == 1
        assert isinstance(outcome.result, Continue)
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_per_subscription_timeout():
    try:
        import asyncio

        called = []

        async def slow(ctx):
            await asyncio.sleep(0.05)
            return Stop(scope=StopScope.MESSAGE)

        async def after(ctx):
            called.append("after")
            return Continue()

        sub_slow = HookSubscription(
            module_name="a",
            subscription_id="p:slow",
            meta=HookMeta(function=slow, point=HookPoint.FINISHED, name="slow", timeout=0.01),
            priority=10,
            available_for=("*",),
            exclude_from=(),
            load=True,
            timeout=0.01,
        )
        sub_after = build_subscription(
            "b", HookMeta(function=after, point=HookPoint.FINISHED, name="after", timeout=1.0), 0
        )
        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={HookPoint.FINISHED: [sub_slow, sub_after]},
        )
        # 不传 dispatch 级 timeout，依赖订阅字段
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg())
        assert "after" in called
        assert isinstance(outcome.result, Continue)
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_named_hook_skips_point_and_disabled():
    try:
        from core.builtins.bot import Bot
        from core.loader import ModulesManager

        called = []

        async def named(ctx):
            called.append("named")
            return "named-ok"

        async def pointed(ctx):
            called.append("pointed")
            return Continue()

        module_name = "__test_named_hook_mod"
        module = _make_module(module_name)
        module.hooks_list.add(HookMeta(function=named, name="cap"))
        module.hooks_list.add(HookMeta(function=pointed, point=str(HookPoint.COMMAND_PREPARE), name="p"))
        ModulesManager.modules[module_name] = module
        try:
            ModulesManager.refresh_modules_hooks()
            # 模块触发只跑具名
            await Bot.Hook.trigger(module_name)
            assert called == ["named"]

            called.clear()
            result = await Bot.Hook.trigger(f"{module_name}.cap")
            assert result == "named-ok" and called == ["named"]

            # 停用后具名也不执行
            module._db_load = False
            called.clear()
            assert await Bot.Hook.trigger(f"{module_name}.cap") is None
            assert called == []
            return True
        finally:
            ModulesManager.modules.pop(module_name, None)
            ModulesManager.refresh_modules_hooks()
            reset_parser_hook_executor()
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_named_hook_uses_shared_execution_contract():
    from core.builtins.hooks import dispatch_module_hook
    from core.constants.exceptions import SessionFinished

    module_name = "__test_named_contract"
    module = _make_module(module_name)
    calls = []

    async def broadcast_bad(ctx):
        calls.append("bad")
        raise RuntimeError("broadcast failure")

    async def broadcast_good(ctx):
        calls.append("good")

    async def restricted(ctx):
        calls.append("restricted")
        return "restricted-result"

    async def direct_failure(ctx):
        raise SessionFinished("stop")

    module.hooks_list.add(HookMeta(function=broadcast_bad, name="bad"))
    module.hooks_list.add(HookMeta(function=broadcast_good, name="good"))
    module.hooks_list.add(HookMeta(function=restricted, name="restricted", available_for=["QQ"], timeout=1))
    module.hooks_list.add(HookMeta(function=direct_failure, name="direct"))
    ModulesManager.modules[module_name] = module
    try:
        ModulesManager.refresh_modules_hooks()
        await dispatch_module_hook(module_name)
        assert calls == ["bad", "good"]

        session = SimpleNamespace(target_from="TEST|Group", client_name="TEST")
        assert await dispatch_module_hook(f"{module_name}.restricted", session_info=session) is None
        assert calls == ["bad", "good"]

        try:
            await dispatch_module_hook(f"{module_name}.direct")
        except SessionFinished:
            return True
        return False
    finally:
        ModulesManager.modules.pop(module_name, None)
        ModulesManager.refresh_modules_hooks()


async def _test_named_hook_timeout_is_enforced():
    import asyncio

    from core.builtins.hooks import dispatch_module_hook

    module_name = "__test_named_timeout"
    module = _make_module(module_name)

    async def slow(ctx):
        await asyncio.sleep(0.05)

    module.hooks_list.add(HookMeta(function=slow, name="slow", timeout=0.01))
    ModulesManager.modules[module_name] = module
    try:
        ModulesManager.refresh_modules_hooks()
        try:
            await dispatch_module_hook(f"{module_name}.slow")
        except asyncio.TimeoutError:
            return True
        return False
    finally:
        ModulesManager.modules.pop(module_name, None)
        ModulesManager.refresh_modules_hooks()


async def _test_event_handler_isolation():
    try:
        from core.builtins.session.info import EventInfo
        from core.loader import ModulesManager
        from core.types.module.component_meta import EventMeta

        called = []

        async def good(info):
            called.append("good")
            return "ok"

        async def bad(info):
            called.append("bad")
            raise RuntimeError("event boom")

        mod_bad = _make_module("__evt_bad")
        mod_good = _make_module("__evt_good")
        mod_bad.events_list.add(EventMeta(function=bad, name="__test_evt"))
        mod_good.events_list.add(EventMeta(function=good, name="__test_evt"))
        ModulesManager.modules["__evt_bad"] = mod_bad
        ModulesManager.modules["__evt_good"] = mod_good
        try:
            ModulesManager.refresh_modules_events()
            info = EventInfo(event_name="__test_evt")
            # available_modules 过滤：无 target_from 时用全部 modules
            results = await ModulesManager.dispatch_event(info)
            assert "good" in called and "bad" in called
            assert results == [None, "ok"] or set(results) >= {"ok", None}
            return True
        finally:
            ModulesManager.modules.pop("__evt_bad", None)
            ModulesManager.modules.pop("__evt_good", None)
            ModulesManager.refresh_modules_events()
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_recovery_target_revalidated():
    try:
        from core.builtins.parser.message import _validate_recovery_target

        msg = _FakeMsg()
        msg.session_info.enabled_modules = []
        msg.session_info.require_enable_modules = True

        off = _make_module("recmod", db_load=False)
        on = _make_module("recmod_on")
        on.base = True

        # 非 base 且场景未启用 → 拒绝
        not_enabled = _make_module("recmod_ne")
        not_enabled.base = False
        assert not await _validate_recovery_target(msg, {"recmod_ne": not_enabled}, "recmod_ne", "recmod_ne x")
        assert not await _validate_recovery_target(msg, {"recmod": off}, "recmod", "recmod x")
        assert await _validate_recovery_target(msg, {"recmod_on": on}, "recmod_on", "recmod_on x")
        assert not await _validate_recovery_target(msg, {}, "missing", "missing x")
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_session_ready_draft_commit():
    try:
        called = []

        async def tag(ctx):
            called.append(1)
            ctx.draft.set_tmp("ready", "1")
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a")},
            parser_hook_subscriptions={
                HookPoint.SESSION_READY: [
                    build_subscription("a", HookMeta(function=tag, point=HookPoint.SESSION_READY, name="tag"), 0)
                ]
            },
        )
        msg = _FakeMsg()
        await ParserHookExecutor(mm).dispatch(HookPoint.SESSION_READY, msg)
        assert called == [1]
        assert msg.session_info.tmp.get("ready") == "1"
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_reload_failure_keeps_old_hooks():
    try:
        from core.loader import ModulesManager
        from core.module_runtime import ModuleRuntimeManager

        called = []

        async def old_hook(ctx):
            called.append(1)
            return Continue()

        module_name = "__reload_fail_mod"
        runtime = ModuleRuntimeManager.get_or_create(module_name)
        old_gen = runtime.generation

        module = _make_module(module_name)
        module.hooks_list.add(HookMeta(function=old_hook, point=str(HookPoint.FINISHED), name="h"))
        ModulesManager.modules[module_name] = module
        try:
            # 初始索引：订阅绑定旧代际
            ModulesManager.refresh_modules_hooks()
            subs = ModulesManager.parser_hook_subscriptions.get(HookPoint.FINISHED, [])
            our = [s for s in subs if s.module_name == module_name]
            assert our and our[0].generation == old_gen

            # 模拟 reload 失败：prepare 出新 staging（新代际）→ restore 旧注册并重建索引
            # （此时旧函数被标成新代际）→ abort 撤销 staging → 再次重建索引
            snapshot = ModuleRuntimeManager.prepare_reload({module_name})
            staged_gen = ModuleRuntimeManager._staging[module_name].generation
            assert staged_gen == old_gen + 1
            ModulesManager.refresh_modules_hooks()  # restore_registrations 内的一次重建
            mid = [
                s
                for s in ModulesManager.parser_hook_subscriptions.get(HookPoint.FINISHED, [])
                if s.module_name == module_name
            ]
            assert mid and mid[0].generation == staged_gen  # 仍绑定 staging（abort 前）
            await ModuleRuntimeManager.abort_reload(snapshot, {module_name})
            ModulesManager.refresh_modules_hooks()  # abort 后的再次重建
            final = [
                s
                for s in ModulesManager.parser_hook_subscriptions.get(HookPoint.FINISHED, [])
                if s.module_name == module_name
            ]
            assert final and final[0].generation == old_gen

            outcome = await get_parser_hook_executor().dispatch(HookPoint.FINISHED, _FakeMsg())
            assert called == [1]
            assert outcome.skipped_stale == 0
            return True
        finally:
            ModulesManager.modules.pop(module_name, None)
            ModulesManager.refresh_modules_hooks()
            ModuleRuntimeManager._current.pop(module_name, None)
            reset_parser_hook_executor()
    except Exception:
        import traceback

        traceback.print_exc()
        return False


@func_case
async def test_parser_hooks(tester: Tester):
    await tester.test(_test_normalize_result, "normalize_result")
    await tester.test(_test_subscription_sort_and_platform, "subscription sort/platform")
    await tester.test(_test_executor_isolates_failures, "executor isolates failures")
    await tester.test(_test_executor_skips_disabled_module_fixed, "executor skips disabled module")
    await tester.test(_test_loader_indexes_point_hooks, "loader indexes point hooks")
    await tester.test(_test_invalid_result_isolated, "invalid result isolated")
    await tester.test(_test_protocol_exception_isolated, "protocol exception isolated")
    await tester.test(_test_timeout_discards_result, "timeout discards late result")
    await tester.test(_test_handled_short_circuits, "Handled short-circuits")
    await tester.test(_test_typo_suggests_close_module, "typo suggests close module")
    await tester.test(_test_stale_generation_skipped, "stale generation skipped")
    await tester.test(_test_per_subscription_timeout, "per-subscription timeout")
    await tester.test(_test_named_hook_skips_point_and_disabled, "named hook skip point/disabled")
    await tester.test(_test_named_hook_uses_shared_execution_contract, "具名 hook 共享执行契约测试")
    await tester.test(_test_named_hook_timeout_is_enforced, "具名 hook 超时约束测试")
    await tester.test(_test_event_handler_isolation, "event handler isolation")
    await tester.test(_test_recovery_target_revalidated, "recovery target revalidated")
    await tester.test(_test_session_ready_draft_commit, "session.ready draft commit")
    await tester.test(_test_cleanup_cancellation_propagates, "cleanup cancellation propagates")
    await tester.test(_test_nested_same_session_dispatch_skipped, "nested same-session dispatch skipped")
    await tester.test(_test_invalid_recovery_fields_rejected, "invalid recovery fields rejected")
    await tester.test(_test_snapshot_build_failure_isolated, "snapshot build failure isolated")
    await tester.test(_test_reload_failure_keeps_old_hooks, "reload failure keeps old hooks")
    await tester.test(_test_missing_runtime_generation_skipped, "missing runtime generation skipped")
    await tester.test(_test_generation_rechecked_between_hooks, "generation rechecked between hooks")
    await tester.test(_test_disabled_rechecked_between_hooks, "disabled state rechecked between hooks")
    await tester.test(_test_outgoing_commit_failure_isolated, "outgoing commit failure isolated")


async def _test_cleanup_cancellation_propagates():
    try:
        import asyncio

        cleanup_entered = asyncio.Event()

        async def slow(ctx):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cleanup_entered.set()
                # 收尾时间超过 50ms 收尾窗口，制造"清理中父被取消"的窗口
                await asyncio.sleep(0.2)
                raise

        mm = SimpleNamespace(
            modules={"a": _make_module("a")},
            parser_hook_subscriptions={
                HookPoint.FINISHED: [
                    build_subscription(
                        "a", HookMeta(function=slow, point=HookPoint.FINISHED, name="slow", timeout=0.01), 0
                    )
                ]
            },
        )
        dispatch_task = asyncio.ensure_future(ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg()))
        # 等 hook 超时并进入异步收尾
        await asyncio.wait_for(cleanup_entered.wait(), timeout=2)
        await asyncio.sleep(0.02)
        dispatch_task.cancel()
        try:
            await dispatch_task
            return False  # 取消被吞掉，dispatch 正常返回
        except asyncio.CancelledError:
            return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_nested_same_session_dispatch_skipped():
    try:
        committed = []
        holder = {}

        async def parent(ctx):
            # 父 hook 内嵌套同会话的 COMMAND_PREPARE 分发
            inner_outcome = await ParserHookExecutor(holder["mm"]).dispatch(HookPoint.COMMAND_PREPARE, ctx.msg)
            committed.append(("inner_executed", inner_outcome.executed))
            raise RuntimeError("parent fails after nested attempt")

        async def child(ctx):
            ctx.draft.set_tmp("child", "committed")
            return Continue()

        holder["mm"] = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.SESSION_READY: [
                    build_subscription("a", HookMeta(function=parent, point=HookPoint.SESSION_READY, name="p"), 0)
                ],
                HookPoint.COMMAND_PREPARE: [
                    build_subscription("b", HookMeta(function=child, point=HookPoint.COMMAND_PREPARE, name="c"), 0)
                ],
            },
        )
        msg = _FakeMsg()
        outcome = await ParserHookExecutor(holder["mm"]).dispatch(HookPoint.SESSION_READY, msg)
        assert outcome.failed == 1
        # 嵌套分发被跳过：child 未执行，tmp 未被提交
        assert ("inner_executed", 0) in committed
        assert "child" not in msg.session_info.tmp
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_invalid_recovery_fields_rejected():
    try:
        from core.builtins.parser.hooks import RecoveryProposal

        async def bad(ctx):
            return RecoveryProposal(trigger_msg=None, command_first_word=[])

        async def after(ctx):
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.COMMAND_UNMATCHED: [
                    build_subscription("a", HookMeta(function=bad, point=HookPoint.COMMAND_UNMATCHED, name="bad"), 0),
                    build_subscription(
                        "b", HookMeta(function=after, point=HookPoint.COMMAND_UNMATCHED, name="after"), 0
                    ),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.COMMAND_UNMATCHED, _FakeMsg())
        assert outcome.failed == 1
        assert isinstance(outcome.result, Continue)
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_snapshot_build_failure_isolated():
    try:
        from core.builtins.parser.hooks import OutgoingPayload

        seen = []

        class _BadChain:
            def copy(self):
                raise RuntimeError("cannot clone")

        async def after(ctx):
            seen.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a")},
            parser_hook_subscriptions={
                HookPoint.OUTGOING_BEFORE_SEND: [
                    build_subscription(
                        "a", HookMeta(function=after, point=HookPoint.OUTGOING_BEFORE_SEND, name="after"), 0
                    )
                ]
            },
        )
        payload = OutgoingPayload(chain=_BadChain())
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.OUTGOING_BEFORE_SEND, _FakeMsg(), outgoing=payload)
        # 快照失败被隔离：hook 未执行，计一次失败，流程未中断
        assert seen == []
        assert outcome.failed == 1
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_missing_runtime_generation_skipped():
    try:
        from core.module_runtime import ModuleRuntimeManager

        module_name = "__missing_runtime_hook"
        called = []

        async def stale(ctx):
            called.append(1)
            return Continue()

        ModuleRuntimeManager._current.pop(module_name, None)
        ModuleRuntimeManager._staging.pop(module_name, None)
        sub = HookSubscription(
            module_name=module_name,
            subscription_id="parser.finished:stale",
            meta=HookMeta(function=stale, point=HookPoint.FINISHED, name="stale"),
            priority=1,
            available_for=("*",),
            exclude_from=(),
            load=True,
            generation=7,
        )
        mm = SimpleNamespace(
            modules={module_name: _make_module(module_name)},
            parser_hook_subscriptions={HookPoint.FINISHED: [sub]},
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg())
        assert called == []
        assert outcome.skipped_stale == 1
        assert module_name not in ModuleRuntimeManager._current
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_generation_rechecked_between_hooks():
    try:
        from core.module_runtime import ModuleRuntimeManager

        first_name = "__generation_recheck_first"
        stale_name = "__generation_recheck_stale"
        ModuleRuntimeManager.get_or_create(first_name)
        stale_runtime = ModuleRuntimeManager.get_or_create(stale_name)
        called = []

        async def replace_runtime(ctx):
            replacement = stale_runtime.next_generation()
            replacement.activate()
            ModuleRuntimeManager._current[stale_name] = replacement
            return Continue()

        async def stale(ctx):
            called.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules={first_name: _make_module(first_name), stale_name: _make_module(stale_name)},
            parser_hook_subscriptions={
                HookPoint.FINISHED: [
                    build_subscription(
                        first_name,
                        HookMeta(function=replace_runtime, point=HookPoint.FINISHED, priority=1, name="first"),
                        0,
                    ),
                    build_subscription(
                        stale_name,
                        HookMeta(function=stale, point=HookPoint.FINISHED, priority=2, name="stale"),
                        1,
                    ),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg())
        assert called == []
        assert outcome.executed == 1
        assert outcome.skipped_stale == 1
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False
    finally:
        from core.module_runtime import ModuleRuntimeManager

        if "first_name" in locals():
            ModuleRuntimeManager._current.pop(first_name, None)
        if "stale_name" in locals():
            ModuleRuntimeManager._current.pop(stale_name, None)


async def _test_outgoing_commit_failure_isolated():
    try:
        from core.builtins.message.chain import MessageChain
        from core.builtins.parser.hooks import OutgoingPayload

        called = []

        class _BadChain:
            def copy(self):
                raise RuntimeError("cannot commit outgoing chain")

        async def bad(ctx):
            ctx.outgoing.chain = _BadChain()
            return Continue()

        async def after(ctx):
            called.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules={"a": _make_module("a"), "b": _make_module("b")},
            parser_hook_subscriptions={
                HookPoint.OUTGOING_BEFORE_SEND: [
                    build_subscription(
                        "a", HookMeta(function=bad, point=HookPoint.OUTGOING_BEFORE_SEND, name="bad"), 0
                    ),
                    build_subscription(
                        "b", HookMeta(function=after, point=HookPoint.OUTGOING_BEFORE_SEND, name="after"), 1
                    ),
                ]
            },
        )
        payload = OutgoingPayload(chain=MessageChain.assign("original"))
        outcome = await ParserHookExecutor(mm).dispatch(
            HookPoint.OUTGOING_BEFORE_SEND,
            _FakeMsg(),
            outgoing=payload,
        )
        assert called == [1]
        assert outcome.failed == 1
        assert outcome.executed == 1
        assert payload.chain.to_str() == "original"
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False


async def _test_disabled_rechecked_between_hooks():
    try:
        called = []
        modules = {"a": _make_module("a"), "b": _make_module("b")}

        async def disable_later(ctx):
            modules["b"]._db_load = False
            return Continue()

        async def later(ctx):
            called.append(1)
            return Continue()

        mm = SimpleNamespace(
            modules=modules,
            parser_hook_subscriptions={
                HookPoint.FINISHED: [
                    build_subscription(
                        "a",
                        HookMeta(function=disable_later, point=HookPoint.FINISHED, priority=1, name="disable"),
                        0,
                    ),
                    build_subscription(
                        "b", HookMeta(function=later, point=HookPoint.FINISHED, priority=2, name="later"), 1
                    ),
                ]
            },
        )
        outcome = await ParserHookExecutor(mm).dispatch(HookPoint.FINISHED, _FakeMsg())
        assert called == []
        assert outcome.executed == 1
        return True
    except Exception:
        import traceback

        traceback.print_exc()
        return False
