from attrs import define

from core.builtins.session.features import Features as FeaturesBase


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = True
    support_mention: bool = True
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = True
    support_markdown: bool = False
    support_reaction: bool = False
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = False
    support_wait: bool = True
