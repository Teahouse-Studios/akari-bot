from core.builtins.session.features import Features
from core.config.base import CoreConfig

dirty_word_check = CoreConfig.enable_dirty_check

features = Features(
    support_image=True,
    support_audio=True,
    support_video=True,
    support_mention=True,
    support_embed=False,
    support_delete=True,
    support_manage=False,
    support_permission_group=True,
    support_markdown=True,
    support_reaction=True,
    support_quote=True,
    support_rss=True,
    support_typing=False,
    support_wait=True,
    support_private_msg=True,
    use_url_md_format=True,
    use_url_manager=False,
    require_check_dirty_words=dirty_word_check,
)
