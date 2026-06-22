from core.builtins.session.features import Features as FeaturesBase

from attrs import define


@define
class Features(FeaturesBase):
    support_image: bool = True
    support_voice: bool = True
    support_mention: bool = True
    support_embed: bool = True
    support_forward: bool = False
    support_delete: bool = True
    support_manage: bool = True
    support_markdown: bool = True
    support_reaction: bool = True
    support_quote: bool = True
    support_rss: bool = True
    support_typing: bool = True
    support_wait: bool = True
    use_url_md_format: bool = False


@define
class SlashFeatures(Features):
    require_enable_modules: bool = False
