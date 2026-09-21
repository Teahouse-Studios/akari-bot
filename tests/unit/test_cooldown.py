"""core.utils.cooldown 冷却系统单元测试。"""

import time

from core.utils.cooldown import CoolDown, _cd_dict
from core.tester import func_case, Tester
from core.tester.mock.session import MockMessageSession


async def _test_cooldown_init():
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("test_cmd", msg, delay=60)
        # 场景维度按消息通道，用户维度按 union：换个平台账号仍受同一份冷却约束，
        # 但仅共享 union 而通道号不同的场景不该互相牵连。
        return (
            cd.key == "test_cmd"
            and cd.delay == 60
            and cd.whole_target is False
            and cd.channel_key == msg.session_info.channel_key
            and cd.sender_union_id == msg.session_info.sender_union_id
        )
    except Exception:
        return False


async def _test_cooldown_init_whole_target():
    try:
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("test_cmd", msg, delay=120, whole_target=True)
        return cd.whole_target is True and cd.delay == 120
    except Exception:
        return False


async def _test_cooldown_check_no_cooldown():
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
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        cd = CoolDown("reset_cmd_xyz", msg, delay=60)
        if cd.check() != 0:
            return False
        cd.reset()
        # 模块每次进入命令都会新建 CoolDown 实例，冷却必须跨实例生效
        remaining = CoolDown("reset_cmd_xyz", msg, delay=60).check()
        # 重置后应恰好剩下一整个冷却时长，模块正是靠这个非 0 值拦截重复调用
        return 0 < remaining <= 60
    except Exception:
        return False


async def _test_cooldown_expired():
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        CoolDown("expired_cmd_xyz", msg, delay=60).reset()
        # 把记录的时间戳拨到冷却时长之前，模拟冷却已经结束
        CoolDown("expired_cmd_xyz", msg, delay=60)._get_cd_dict().ts = time.time() - 61
        return CoolDown("expired_cmd_xyz", msg, delay=60).check() == 0
    except Exception:
        return False


async def _test_cooldown_check_readonly():
    try:
        _cd_dict.clear()
        msg = MockMessageSession("~test")
        await msg.async_init("~test")
        if CoolDown("readonly_cmd_xyz", msg, delay=60).check() != 0:
            return False
        return len(_cd_dict) == 0
    except Exception:
        return False


async def _test_cooldown_get_cd_dict_creates():
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
    """core.utils.cooldown: CoolDown 冷却系统测试"""
    await tester.test(_test_cooldown_init, "CoolDown 初始化测试")
    await tester.test(_test_cooldown_init_whole_target, "CoolDown whole_target 初始化测试")
    await tester.test(_test_cooldown_check_no_cooldown, "CoolDown 无冷却时 check 测试")
    await tester.test(_test_cooldown_reset, "CoolDown reset 计时测试")
    await tester.test(_test_cooldown_expired, "CoolDown 冷却结束测试")
    await tester.test(_test_cooldown_check_readonly, "CoolDown check 只读测试")
    await tester.test(_test_cooldown_get_cd_dict_creates, "CoolDown _get_cd_dict 创建测试")
    await tester.test(_test_cooldown_multiple_keys, "CoolDown 多 key 独立测试")
    return tester
