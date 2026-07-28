from attrs import define

from core.builtins.session.features import Features as FeaturesBase
from bots.qqbot.config import QQBotConfig
from core.config.base import CoreConfig

dirty_word_check = CoreConfig.enable_dirty_check
qq_use_markdown = QQBotConfig.qq_use_markdown


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = False
    support_mention: bool = True
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = False
    support_markdown: bool = True
    support_reaction: bool = False
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = False
    support_wait: bool = True
    support_private_msg: bool = True
    require_check_dirty_words: bool = dirty_word_check
    use_url_md_format: bool = qq_use_markdown
