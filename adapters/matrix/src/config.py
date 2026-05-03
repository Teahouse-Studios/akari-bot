from core.config.decorator import on_config
from core.constants.default import matrix_homeserver_default, matrix_user_default


@on_config("matrix", "bot", False)
class MatrixConfig:
    enable: bool = False
    matrix_homeserver: str = matrix_homeserver_default
    matrix_user: str = matrix_user_default
    matrix_device_name: str = ""


@on_config("matrix", "bot", True)
class MatrixSecretConfig:
    matrix_device_id: str = ""
    matrix_token: str = ""
    matrix_megolm_backup_passphrase: str = ""
