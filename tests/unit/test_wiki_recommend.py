"""wiki 推荐绑定列表单元测试 - 按钮数据构造与发出门槛。

按钮的下发门槛此前由「客户端名为 QQBot 且支持 Markdown」就地判定，现已摊平为
support_button 一项，故用例改按该标志构造会话，客户端名不再参与判定。按钮回流经
interaction 事件另建会话，其可用前缀与常规消息入口不同，前缀相关的用例即为守住这条不变量。
"""

from unittest.mock import patch

from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.session.internal import MessageSession
from core.builtins.utils import command_prefix
from core.constants.exceptions import SessionFinished
from core.tester import func_case, Tester
from core.utils.button import DEFAULT_BUTTONS_PER_ROW
from modules.wiki.utils.recommend import (
    RECOMMENDED_WIKIS,
    finish_with_start_wiki_not_set,
    get_recommend_button_data,
)


async def _probe(target_id: str, client_name: str, support_button: bool, is_admin: bool) -> dict:
    """
    跑一遍未设置起始 Wiki 的收尾流程，捕获它交给 finish 的消息与按钮数据。

    :param target_id: 场景 ID，各用例互不相同以免共用 union。
    :param client_name: 客户端名。判定已不再读取此项，保留仅为贴近真实会话。
    :param support_button: 会话是否具备按钮能力。
    :param is_admin: 发送者是否具备管理权限。
    :return: 含 prompts 与 button_data 两个键的字典。
    """
    session_info = await SessionInfo.assign(
        target_id=target_id,
        target_from=f"{client_name}|Group",
        client_name=client_name,
        sender_id=f"{client_name}|1",
        features=Features(support_button=support_button),
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
    """测试按钮数据 - 条目数超过单行上限时按可读性上限分行并均分

    分行已收归 core.utils.button，此处只验证 wiki 侧确实经由该工具产出，
    具体的均分规则由 tests/unit/test_button_arrange.py 把关。
    """
    try:
        count = DEFAULT_BUTTONS_PER_ROW * 2 + 1
        wikis = [(f"Wiki {i}", f"https://example{i}.invalid/api.php") for i in range(count)]
        with patch("modules.wiki.utils.recommend.RECOMMENDED_WIKIS", wikis):
            rows = get_recommend_button_data()
        # 7 个按钮在上限 3 之下分作三行，余数均摊到首行
        return [len(row) for row in rows] == [3, 2, 2]

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


async def _test_other_client_gets_buttons():
    """测试发出门槛 - 判定只看按钮能力，非 QQ 官方机器人声明后同样下发

    这条守住摊平本身：新增支持按钮的平台只需在自己的 features.py 中声明，无须回头改动模块。
    """
    try:
        captured = await _probe("TEST|Group|recommend_other", "TEST", True, True)
        keys = [element.key for element in captured["prompts"]]
        return captured["button_data"] == get_recommend_button_data() and keys == [
            "wiki.message.set.not_set",
            "wiki.message.set.not_set.recommend",
        ]

    except Exception:
        return False


async def _test_button_unsupported_gets_no_buttons():
    """测试发出门槛 - 会话不具备按钮能力时不下发按钮

    对应 QQ 官方机器人关闭 qq_use_markdown 的情形：消息走纯文本路径，按钮无从附带。
    """
    try:
        captured = await _probe("QQBot|Group|recommend_nobutton", "QQBot", False, True)
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
    await tester.test(_test_other_client_gets_buttons, "其他平台声明后有按钮测试")
    await tester.test(_test_button_unsupported_gets_no_buttons, "无按钮能力时无按钮测试")

    return tester
