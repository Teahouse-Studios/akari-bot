from core.config.decorator import on_config


@on_config("discord", "bot", False)
class DiscordConfig:
    enable: bool = False


@on_config("discord", "bot", True)
class DiscordSecretConfig:
    discord_token: str = ""
