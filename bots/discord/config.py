from core.config.decorator import on_bot_config


@on_bot_config("discord")
class DiscordConfig:
    enable: bool = False


@on_bot_config("discord", secret=True)
class DiscordSecretConfig:
    discord_token: str = ""
