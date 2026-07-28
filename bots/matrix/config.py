from core.config.decorator import on_bot_config
from core.constants.default import matrix_homeserver_default, matrix_user_default


@on_bot_config("matrix")
class MatrixConfig:
    enable: bool = False
    matrix_homeserver: str = matrix_homeserver_default
    matrix_user: str = matrix_user_default
    matrix_device_name: str = ""


@on_bot_config("matrix", secret=True)
class MatrixSecretConfig:
    matrix_device_id: str = ""
    matrix_token: str = ""
    matrix_megolm_backup_passphrase: str = ""
