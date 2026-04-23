from core.config.decorator import on_config
from core.constants.default import qq_host_default


@on_config("onebot", "bot", False)
class AiocqhttpConfig:
    enable: bool = False
    qq_host: str = qq_host_default
    qq_enable_listening_self_message: bool = False
    qq_enable_temp_session: bool = False
    qq_allow_approve_friend: bool = False
    qq_allow_approve_group_invite: bool = False
    qq_typing_emoji: int = 181
    qq_limited_emoji: int = 10060
    qq_initiative_msg_cooldown: int = 10


@on_config("onebot", "bot", True)
class AiocqhttpSecretConfig:
    qq_access_token: str = ""
