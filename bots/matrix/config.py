from core.config.decorator import on_config


@on_config("matrix", "bot", False)
class MatrixConfig:
    enable: bool = False
    matrix_homeserver: str = "https://matrix.org"
    matrix_user: str = "@akaribot:matrix.org"
    matrix_device_name: str = ""


@on_config("matrix", "bot", True)
class MatrixSecretConfig:
    matrix_device_id: str = ""
    matrix_token: str = ""
    matrix_megolm_backup_passphrase: str = ""
