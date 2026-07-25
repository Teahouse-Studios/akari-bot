"""core.cooldown 冷却系统单元测试。"""

from core.cooldown import CoolDown, _cd_dict
from core.tester import func_case, Tester
from core.tester.mock.session import MockMessageSession


async def _test_cooldown_init():
    """CoolDown: 初始化属性"""
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("test_cmd", msg, delay=60)
        return (
            cd.key == "test_cmd"
            and cd.delay == 60
            and cd.whole_target is False
            and cd.target_id == msg.session_info.target_id
            and cd.sender_id == msg.session_info.sender_id
        )
    except Exception:
        return False


async def _test_cooldown_init_whole_target():
    """CoolDown: whole_target=True 初始化"""
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("test_cmd", msg, delay=120, whole_target=True)
        return cd.whole_target is True and cd.delay == 120
    except Exception:
        return False


async def _test_cooldown_check_no_cooldown():
    """CoolDown: 未设置冷却时 check() 应返回 0"""
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("fresh_cmd_xyz", msg, delay=60)
        remaining = cd.check()
        return remaining == 0
    except Exception:
        return False


async def _test_cooldown_reset():
    """CoolDown: reset() 后 check() 应返回 0"""
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("reset_cmd_xyz", msg, delay=60)
        cd.reset()
        remaining = cd.check()
        return remaining == 0
    except Exception:
        return False


async def _test_cooldown_get_cd_dict_creates():
    """CoolDown: _get_cd_dict 应创建嵌套结构"""
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("dict_create_test", msg, delay=30)
        cd_dict = cd._get_cd_dict()
        from core.utils.container import ExpiringTempDict

        return isinstance(cd_dict, ExpiringTempDict)
    except Exception:
        return False


async def _test_cooldown_multiple_keys():
    """CoolDown: 不同 key 应独立"""
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd1 = CoolDown("key_a", msg, delay=60)
        cd2 = CoolDown("key_b", msg, delay=120)
        d1 = cd1._get_cd_dict()
        d2 = cd2._get_cd_dict()
        return d1 is not d2
    except Exception:
        return False


@func_case
async def test_cooldown(tester: Tester):
    """core.cooldown: CoolDown 冷却系统测试"""
    await tester.test(_test_cooldown_init, "CoolDown 初始化测试")
    await tester.test(_test_cooldown_init_whole_target, "CoolDown whole_target 初始化测试")
    await tester.test(_test_cooldown_check_no_cooldown, "CoolDown 无冷却时 check 测试")
    await tester.test(_test_cooldown_reset, "CoolDown reset 测试")
    await tester.test(_test_cooldown_get_cd_dict_creates, "CoolDown _get_cd_dict 创建测试")
    await tester.test(_test_cooldown_multiple_keys, "CoolDown 多 key 独立测试")
    return tester
