from attrs import define

from core.builtins.session.features import Features as FeaturesBase
from core.config import Config

dirty_word_check = Config("enable_dirty_check", False)
use_url_manager = Config("enable_urlmanager", False)
qq_use_markdown = Config("qq_use_markdown", False, bool, table_name="bot_qqbot")


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
    require_check_dirty_words: bool = dirty_word_check
    use_url_md_format: bool = qq_use_markdown
