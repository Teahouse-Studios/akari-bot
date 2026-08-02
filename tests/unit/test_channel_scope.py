"""union 与消息通道的作用域单元测试 - 内存态按通道、花瓣额度按 union（需要数据库）。"""

import asyncio
from unittest.mock import patch

import core.utils.petal as petal_module
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.session.tasks import SessionTaskManager
from core.cooldown import CoolDown, _cd_dict
from core.database.models import SenderUnionInfo, StoredData, TargetUnionInfo, TargetUnionBind
from core.game import PlayState
from core.tester import func_case, Tester


async def _session(target_id: str, client: str) -> MessageSession:
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client}|Group",
        client_name=client,
        sender_id=f"{client}|1",
        create=True,
    )
    return MessageSession(session_info=session_info)


async def _states_shared(prefix: str) -> tuple[bool, bool, bool]:
    """
    判断同一 union 下的两个平台场景是否共用冷却、游戏状态与等待任务。
    """
    first = await _session(f"{prefix}1|Group|x", f"{prefix}1")
    second = await _session(f"{prefix}2|Group|y", f"{prefix}2")

    _cd_dict.clear()
    SessionTaskManager._task_list.clear()

    # check() 只按底层字典是否有内容判断，无法用来观测归属，故直接比较冷却桶本身
    shared_cooldown = (
        CoolDown("probe", first, delay=60, whole_target=True)._get_cd_dict()
        is CoolDown("probe", second, delay=60, whole_target=True)._get_cd_dict()
    )

    PlayState("probe", first).enable()
    shared_game = PlayState("probe", second).check()
    PlayState("probe", first).disable()

    SessionTaskManager.add_task(first, asyncio.Event(), all_=True, timeout=60)
    shared_task = second.session_info.channel_key in SessionTaskManager.get()
    SessionTaskManager._task_list.clear()

    return shared_cooldown, shared_game, shared_task


async def _test_states_isolated_across_channels():
    """测试作用域 - 同 union 但通道号不同的场景不应共用内存态"""
    try:
        union = await TargetUnionInfo.resolve_union("CHA1|Group|x")
        await union.bind_id("CHA2|Group|y")
        # 绑定后默认各占一号，即默认谁也不与谁合并，此时只是共享配置而非同一个现实场景
        return await _states_shared("CHA") == (False, False, False)

    except Exception:
        return False


async def _test_states_shared_within_channel():
    """测试作用域 - 并入同一消息通道后应共用内存态"""
    try:
        union = await TargetUnionInfo.resolve_union("CHB1|Group|x")
        await union.bind_id("CHB2|Group|y")
        await TargetUnionBind.filter(target_id="CHB2|Group|y").update(channel_id=1)
        return await _states_shared("CHB") == (True, True, True)

    except Exception:
        return False


async def _test_petal_quota_shared_across_platforms():
    """测试作用域 - 花瓣每日额度按 union 共享，不随平台账号翻倍"""
    union = await SenderUnionInfo.resolve_union("PETALA|1")
    await union.bind_id("PETALB|2")

    async def gain(sender_id: str, amount: int):
        session_info = await SessionInfo.assign(
            target_id="PETALA|Group|1", target_from="PETALA|Group", client_name="PETALA", create=True
        )
        sender_union_info = await SenderUnionInfo.resolve_union(sender_id)
        session_info.sender_id = sender_id
        session_info.sender_union_info = sender_union_info
        session_info.sender_union_id = sender_union_info.union_id
        return await petal_module.gained_petal(MessageSession(session_info=session_info), amount)

    config = type("Config", (), {"enable_petal": True, "enable_get_petal": True, "petal_gained_limit": 5})
    try:
        with patch.object(petal_module, "CoreConfig", config):
            await gain("PETALA|1", 5)
            # 花瓣余额挂在 union 上，日额度若仍按平台账号记账，绑几个平台就能领几倍
            reached_limit = "limit" in str(await gain("PETALB|2", 5))
        return reached_limit and (await SenderUnionInfo.resolve_union("PETALA|1")).petal == 5

    except Exception:
        return False
    finally:
        await StoredData.filter(stored_key__startswith=f"{petal_module.PETAL_STORE_SCOPE}|").delete()


@func_case
async def test_channel_scope(tester: Tester):
    """core: union 与消息通道的作用域测试"""
    await tester.test(_test_states_isolated_across_channels, "跨通道内存态隔离测试")
    await tester.test(_test_states_shared_within_channel, "同通道内存态共享测试")
    await tester.test(_test_petal_quota_shared_across_platforms, "花瓣额度按 union 共享测试")

    return tester
