from core.config.decorator import on_config


@on_config("smtp")
class SMTPConfig:
    enable: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_sender: str = ""
    smtp_ssl: bool = False
    smtp_starttls: bool = True


@on_config("smtp", secret=True)
class SMTPSecretConfig:
    smtp_password: str = ""
    smtp_recipients: list = []
