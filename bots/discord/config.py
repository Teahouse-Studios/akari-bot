from core.config.decorator import on_config

@on_config("discord", "bot", False)
class DiscordConfig:
    """
    Discord bot configuration.
    """
    enable: bool = False

@on_config("discord", "bot", True)
class DiscordSecretConfig:
    """
    Discord bot secret configuration.
    """
    discord_token: str = ""
