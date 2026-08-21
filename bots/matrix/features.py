from core.builtins.session.features import Features

features = Features(
    support_image=True,
    support_voice=True,
    support_mention=True,
    support_embed=False,
    support_forward=False,
    support_delete=True,
    # Matrix 目前实现踢出／封禁，但没有实现 Captcha 所需的临时限制与解除限制。
    support_manage=False,
    support_markdown=False,
    support_reaction=True,
    support_quote=True,
    support_rss=True,
    support_typing=False,
    support_wait=True,
    support_private_msg=True,
)
