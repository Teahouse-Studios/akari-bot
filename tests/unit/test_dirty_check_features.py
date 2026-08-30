"""bots/*/features 单元测试 - 平台能力开关的传递（需要数据库）。"""

from core.alive import Alive
from core.builtins.bot import Bot
from core.builtins.converter import converter
from core.builtins.session.features import Features
from core.builtins.session.internal import FetchedMessageSession
from core.tester import func_case, Tester

FLAG = "require_check_dirty_words"


async def _test_flag_reaches_fetched_session():
    """测试文字过滤 - 平台声明的开关须传递到主动推送会话上"""
    alive = Alive.values.copy()
    try:
        Alive.values.clear()
        # 主动推送的会话没有触发消息，能力标志只能从保活信号里带过来，
        # wikilog 等模块的 check() 正是据此判断要不要过滤。
        for client, flag in (("DIRTYON", True), ("DIRTYOFF", False)):
            features = Features(**{FLAG: flag})
            Alive.refresh_alive(
                client,
                target_prefix_list=[f"{client}|Group"],
                sender_prefix_list=[client],
                ctx_slot_index=1,
                features=converter.structure(converter.unstructure(features, Features), Features),
            )

        for client, flag in (("DIRTYON", True), ("DIRTYOFF", False)):
            fetched = await Bot.fetch_target(f"{client}|Group|1", create=True)
            if not fetched:
                return False
            session = await FetchedMessageSession.from_session_info(fetched)
            if getattr(session.session_info, FLAG) is not flag:
                return False
        return True

    except Exception:
        return False
    finally:
        Alive.values.clear()
        Alive.values.update(alive)


async def _test_wiki_content_check_respects_dirty_word_feature():
    """Wiki 内容检查须受 require_check_dirty_words 开关控制。"""
    from modules.wiki.utils.wikilib import WikiLib

    class SessionInfo:
        require_check_dirty_words = False

    class Session:
        session_info = SessionInfo()

    wiki = WikiLib("https://example.test/w/api.php")
    wiki.wiki_info.is_allowed = False
    if wiki.should_check_content(Session()):
        return False

    SessionInfo.require_check_dirty_words = True
    if not wiki.should_check_content(Session()):
        return False

    return True


@func_case
async def test_dirty_check_features(tester: Tester):
    """bots.features: 平台能力开关测试"""
    await tester.test(_test_flag_reaches_fetched_session, "开关传递到主动推送会话测试")
    await tester.test(_test_wiki_content_check_respects_dirty_word_feature, "Wiki 内容检查开关测试")

    return tester
