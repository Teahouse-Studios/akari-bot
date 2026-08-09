from typing import TYPE_CHECKING

from attr import evolve

from bots.qqbot.config import QQBotConfig
from core.builtins.session.features import Features
from core.config.base import CoreConfig

if TYPE_CHECKING:
    from core.builtins.session.info import SessionInfo

dirty_word_check = CoreConfig.enable_dirty_check
qq_use_markdown = QQBotConfig.qq_use_markdown

features = Features(
    support_image=True,
    support_voice=False,
    support_mention=True,
    support_embed=False,
    support_forward=False,
    support_delete=True,
    support_manage=False,
    support_markdown=True,
    support_markdown_table=qq_use_markdown,
    support_reaction=False,
    support_quote=True,
    support_rss=True,
    support_typing=False,
    support_wait=True,
    support_handle_message_nodes=qq_use_markdown,
    support_private_msg=True,
    support_action_text=qq_use_markdown,
    support_button=qq_use_markdown,
    support_markdown_toggle=qq_use_markdown,
    require_check_dirty_words=dirty_word_check,
    use_url_md_format=qq_use_markdown,
    use_url_manager=CoreConfig.enable_urlmanager,
)

# 群主未开启「读取全部消息」权限时，机器人只收到提及自身的消息。平台不提供查询主动推送
# 权限的接口，而两类权限通常同批开通，故以此为判据一并关闭推送与正则模块。
group_disable_read_all_message_features = evolve(
    features,
    support_rss=False,
    read_all_messages=False,
)

guild_features = evolve(
    features,
    support_markdown=False,
    support_markdown_table=False,
    support_action_text=False,
    support_button=False,
    use_url_md_format=False,
)


def resolve_features(session_info: "SessionInfo", base: Features = features) -> Features:
    """
    按用户的 markdown 偏好调整平台能力。

    markdown 消息承载了行内指令操作、底部按钮与内嵌图片，用户关闭后这些能力一并失效，
    消息改走纯文本路径。``support_markdown`` 一并置假，既作发送路径的判据，也使各模块
    停止转义 markdown 元字符。

    ``support_markdown_toggle`` 不在覆盖之列：它一旦随之关闭，设置面板中的该行会消失，
    用户便再无入口把 markdown 开回来。

    :param session_info: 会话信息，其用户 union 承载该偏好。
    :param base: 覆盖所基于的能力集，供与其他覆盖叠加。
    :return: 调整后的能力集；无须调整时原样返回 base。
    """
    if not qq_use_markdown or not session_info.sender_union_info:
        return base
    if session_info.sender_union_info.sender_data.get("use_markdown", True):
        return base
    return evolve(
        base,
        support_markdown=False,
        support_markdown_table=False,
        support_action_text=False,
        support_button=False,
        use_url_md_format=False,
    )
