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
    # 指令操作标签只在 markdown 消息中生效，关闭 markdown 时平台确实不具备该能力。
    # 此处若恒为真，模块侧会照常构造可点击的内容，发送时却走纯文本路径就地降级。
    support_action_text=qq_use_markdown,
    require_check_dirty_words=dirty_word_check,
    use_url_md_format=qq_use_markdown,
)

group_disable_read_all_message_features = evolve(features, require_enable_modules=False)
