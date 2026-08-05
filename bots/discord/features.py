from attrs import evolve

from core.builtins.session.features import Features

features = Features(
    support_image=True,
    support_voice=True,
    support_mention=True,
    support_embed=True,
    support_forward=False,
    support_delete=True,
    support_manage=True,
    support_markdown=True,
    support_reaction=True,
    support_quote=True,
    support_rss=True,
    support_typing=True,
    support_wait=True,
    support_private_msg=True,
    support_button=True,
    use_url_md_format=False,
)

slash_features = evolve(features, require_enable_modules=False)
