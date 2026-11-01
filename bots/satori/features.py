from core.builtins.session.features import Features
from core.config.base import CoreConfig

features = Features(
    support_image=True,
    support_audio=True,
    support_video=True,
    support_mention=True,
    support_delete=True,
    support_manage=True,
    support_reaction=True,
    support_quote=True,
    support_rss=True,
    support_wait=True,
    support_private_msg=True,
    support_typing=True,
    use_url_manager=CoreConfig.enable_urlmanager,
    require_check_dirty_words=CoreConfig.enable_dirty_check,
)
