from attrs import define

from core.builtins.session.features import Features as FeaturesBase


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = False
    support_mention: bool = False
    support_embed: bool = False
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = False
    support_markdown: bool = True
    support_reaction: bool = True
    support_quote: bool = False
    support_rss: bool = False
    support_typing: bool = True
    support_wait: bool = True
    use_url_md_format: bool = True
