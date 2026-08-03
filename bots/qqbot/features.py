from attr import evolve

from bots.qqbot.config import QQBotConfig
from core.builtins.session.features import Features
from core.config.base import CoreConfig

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
    support_reaction=False,
    support_quote=True,
    support_rss=True,
    support_typing=False,
    support_wait=True,
    support_private_msg=True,
    support_action_text=qq_use_markdown,
    support_button=qq_use_markdown,
    require_check_dirty_words=dirty_word_check,
    use_url_md_format=qq_use_markdown,
)

# 群主未开启「读取全部消息」权限时，机器人只收到提及自身的消息。平台不提供查询主动推送
# 权限的接口，而两类权限通常同批开通，故以此为判据一并关闭推送与正则模块。
group_disable_read_all_message_features = evolve(
    features,
    support_rss=False,
    read_all_messages=False,
)
