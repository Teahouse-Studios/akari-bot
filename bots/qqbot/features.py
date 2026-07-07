from attrs import define

from core.builtins.session.features import Features as FeaturesBase
from core.config import Config


dirty_word_check = Config("enable_dirty_check", False)
use_url_manager = Config("enable_urlmanager", False)


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = False
    support_mention: bool = True
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = False
    support_markdown: bool = False
    support_reaction: bool = False
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = False
    support_wait: bool = False
    require_check_dirty_words: bool = dirty_word_check
