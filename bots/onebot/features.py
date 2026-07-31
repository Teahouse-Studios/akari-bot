from core.builtins.session.features import Features
from core.config.base import CoreConfig

use_url_manager = CoreConfig.enable_urlmanager
dirty_word_check = CoreConfig.enable_dirty_check

features = Features(
    support_image=True,
    support_voice=True,
    support_mention=True,
    support_embed=False,
    support_forward=True,
    support_delete=True,
    support_manage=True,
    support_markdown=False,
    support_reaction=True,
    support_quote=True,
    support_rss=True,
    support_typing=True,
    support_wait=True,
    support_private_msg=True,
    support_handle_message_nodes=True,
    use_url_manager=use_url_manager,
    require_check_dirty_words=dirty_word_check,
)
