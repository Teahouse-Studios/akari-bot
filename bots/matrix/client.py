from urllib.parse import urlparse
from nio import AsyncClient, AsyncClientConfig

from bots.matrix.config import MatrixConfig, MatrixSecretConfig
from core.config.base import CoreSecretConfig
from core.constants.path import assets_path
from core.logger import Logger

homeserver = MatrixConfig.matrix_homeserver
user = MatrixConfig.matrix_user
device_id = MatrixSecretConfig.matrix_device_id
device_name = MatrixConfig.matrix_device_name
token = MatrixSecretConfig.matrix_token
megolm_backup_passphrase = MatrixSecretConfig.matrix_megolm_backup_passphrase
proxy = CoreSecretConfig.proxy

store_path = assets_path / "private" / "matrix" / "matrix_store"
store_path_nio = store_path / "nio"
store_path_megolm_backup = store_path / "megolm_backup"

store_path_next_batch = store_path / "next_batch.txt"

store_path.mkdir(parents=True, exist_ok=True)
store_path_nio.mkdir(parents=True, exist_ok=True)
if megolm_backup_passphrase:
    store_path_megolm_backup.mkdir(parents=True, exist_ok=True)
    if len(megolm_backup_passphrase) <= 10:
        Logger.warning("matrix_megolm_backup_passphrase is too short. It is insecure.")
else:
    Logger.warning(
        "Matrix megolm backup is not setup. It is recommended to set matrix_megolm_backup_passphrase to a unique passphrase."
    )

if homeserver.endswith("/"):
    Logger.warning("The matrix_homeserver ends with a slash(/), and this may cause M_UNRECOGNIZED error.")
homeserver_host = urlparse(homeserver).hostname
matrix_bot: AsyncClient = AsyncClient(
    homeserver, user, store_path=store_path_nio, config=AsyncClientConfig(store_sync_tokens=True), proxy=proxy
)
matrix_bot.restore_login(user, device_id, token)
if matrix_bot.olm:
    Logger.info("Matrix E2E encryption support is available.")
else:
    Logger.info("Matrix E2E encryption support is not available.")
