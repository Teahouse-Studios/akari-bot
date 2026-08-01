"""wiki 推荐绑定列表单元测试 - 按钮数据构造与发出门槛。

按钮仅在 QQ 官方机器人上下发，而测试会话的客户端名恒为 TEST，集成测试覆盖不到该分支，
故此处直接构造 QQBot 会话求证。按钮回流经 interaction 事件另建会话，其可用前缀与常规
消息入口不同，前缀相关的用例即为守住这条不变量。
"""

from unittest.mock import patch

from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from modules.wiki.utils.recommend import (
    MAX_BUTTONS_PER_ROW,
    RECOMMENDED_WIKIS,
    finish_with_start_wiki_not_set,
    get_recommend_button_data,
)


async def _probe(target_id: str, client_name: str, support_markdown: bool, is_admin: bool) -> dict:
    """
    跑一遍未设置起始 Wiki 的收尾流程，捕获它交给 finish 的消息与按钮数据。

    :param target_id: 场景 ID，各用例互不相同以免共用 union。
    :param client_name: 客户端名。
    :param support_markdown: 会话是否支持 Markdown。
    :param is_admin: 发送者是否具备管理权限。
    :return: 含 prompts 与 button_data 两个键的字典。
    """
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client_name}|Group",
        client_name=client_name,
        sender_id=f"{client_name}|1",
        features=Features(support_markdown=support_markdown),
    )
    msg = MessageSession(session_info=session_info)
    captured = {}

    async def _finish(self, message_chain=None, **kwargs):
        captured["prompts"] = message_chain
        captured["button_data"] = kwargs.get("button_data")
        raise SessionFinished

    async def _check_permission(self):
        return is_admin

    with (
        patch.object(MessageSession, "finish", _finish),
        patch.object(MessageSession, "check_permission", _check_permission),
    ):
        try:
            await finish_with_start_wiki_not_set(msg)
        except SessionFinished:
            pass
    return captured


async def _test_button_data_shape():
    """测试按钮数据 - 键为 Wiki 名称，值为设置起始 Wiki 的命令"""
    try:
        rows = get_recommend_button_data()
        if len(rows) != 1:
            return False
        name, url = RECOMMENDED_WIKIS[0]
        return rows[0] == {name: f"{command_prefix[0]}wiki set {url}"}

    except Exception:
        return False


async def _test_button_rows_are_split():
    """测试按钮数据 - 条目数超过单行上限时按上限分行"""
    try:
        wikis = [(f"Wiki {i}", f"https://example{i}.invalid/api.php") for i in range(MAX_BUTTONS_PER_ROW + 2)]
        with patch("modules.wiki.utils.recommend.RECOMMENDED_WIKIS", wikis):
            rows = get_recommend_button_data()
        return len(rows) == 2 and len(rows[0]) == MAX_BUTTONS_PER_ROW and len(rows[1]) == 2

    except Exception:
        return False


async def _test_button_prefix_reachable_from_interaction():
    """测试按钮回流 - 按钮命令的前缀在 interaction 所建会话中可被识别"""
    try:
        # 与 bots/qqbot/bot.py 的 on_interaction_create 一致：不指定前缀，
        # 故会话取到的是全局配置的前缀，而非常规消息入口所用的斜杠前缀。
        session_info = await SessionInfo.assign(
            target_id="QQBot|Group|recommend_interaction",
            target_from="QQBot|Group",
            client_name="QQBot",
            sender_id="QQBot|1",
        )
        data = next(iter(get_recommend_button_data()[0].values()))
        return any(data.startswith(prefix) for prefix in session_info.prefixes)

    except Exception:
        return False


async def _test_admin_gets_buttons():
    """测试发出门槛 - QQ 官方机器人上的管理员收到按钮与引导文案"""
    try:
        captured = await _probe("QQBot|Group|recommend_admin", "QQBot", True, True)
        keys = [element.key for element in captured["prompts"]]
        return captured["button_data"] == get_recommend_button_data() and keys == [
            "wiki.message.set.not_set",
            "wiki.message.set.not_set.recommend",
        ]

    except Exception:
        return False


async def _test_non_admin_gets_no_buttons():
    """测试发出门槛 - 无管理权限者只收到原有提示"""
    try:
        captured = await _probe("QQBot|Group|recommend_member", "QQBot", True, False)
        keys = [element.key for element in captured["prompts"]]
        return not captured["button_data"] and keys == ["wiki.message.set.not_set"]

    except Exception:
        return False


async def _test_other_client_gets_no_buttons():
    """测试发出门槛 - 其余平台的输出不受影响，管理员亦无按钮"""
    try:
        captured = await _probe("TEST|Group|recommend_other", "TEST", True, True)
        keys = [element.key for element in captured["prompts"]]
        return not captured["button_data"] and keys == ["wiki.message.set.not_set"]

    except Exception:
        return False


async def _test_markdown_off_gets_no_buttons():
    """测试发出门槛 - 会话不支持 Markdown 时不下发按钮"""
    try:
        captured = await _probe("QQBot|Group|recommend_nomd", "QQBot", False, True)
        keys = [element.key for element in captured["prompts"]]
        return not captured["button_data"] and keys == ["wiki.message.set.not_set"]

    except Exception:
        return False


@func_case
async def test_wiki_recommend(tester: Tester):
    """wiki 推荐绑定列表：按钮数据与发出门槛测试"""
    await tester.test(_test_button_data_shape, "按钮数据结构测试")
    await tester.test(_test_button_rows_are_split, "按钮分行测试")
    await tester.test(_test_button_prefix_reachable_from_interaction, "按钮前缀可识别测试")
    await tester.test(_test_admin_gets_buttons, "管理员收到按钮测试")
    await tester.test(_test_non_admin_gets_no_buttons, "非管理员无按钮测试")
    await tester.test(_test_other_client_gets_no_buttons, "其他平台无按钮测试")
    await tester.test(_test_markdown_off_gets_no_buttons, "无 Markdown 无按钮测试")

    return tester
