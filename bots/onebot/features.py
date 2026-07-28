from attrs import define

from core.builtins.session.features import Features as FeaturesBase
from core.config.base import CoreConfig

use_url_manager = CoreConfig.enable_urlmanager
dirty_word_check = CoreConfig.enable_dirty_check


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = True
    support_mention: bool = True
    support_embed: bool = False
    support_forward: bool = True
    support_delete: bool = True
    support_manage: bool = True
    support_markdown: bool = False
    support_reaction: bool = True
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = True
    support_wait: bool = True
    support_private_msg: bool = True
    support_handle_message_nodes: bool = True
    use_url_manager: bool = use_url_manager
    require_check_dirty_words: bool = dirty_word_check
