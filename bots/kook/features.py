from core.builtins.session.features import Features as FeaturesBase
from core.config import Config

from attrs import define

use_url_manager = Config("enable_urlmanager", False)


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = True
    support_mention: bool = True
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = False
    support_markdown: bool = True
    support_reaction: bool = True
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = True
    support_wait: bool = True
    use_url_manager: bool = use_url_manager
    use_url_md_format: bool = True
