import urllib3
from nio import AsyncClient, AsyncClientConfig

from core.config import Config
from core.constants.path import assets_path
from core.constants.default import matrix_homeserver_default, matrix_user_default
from core.logger import Logger

homeserver = Config("matrix_homeserver", matrix_homeserver_default, table_name="bot_matrix")
user = Config("matrix_user", matrix_user_default, table_name="bot_matrix")
device_id = Config("matrix_device_id", cfg_type=str, secret=True, table_name="bot_matrix")
device_name = Config("matrix_device_name", cfg_type=str, table_name="bot_matrix")
token = Config("matrix_token", cfg_type=str, secret=True, table_name="bot_matrix")
megolm_backup_passphrase = Config(
    "matrix_megolm_backup_passphrase",
    cfg_type=str,
    secret=True,
    table_name="bot_matrix",
)
proxy = Config("proxy", cfg_type=str, secret=True)

store_path = assets_path / "private" / "matrix" / "matrix_store"
store_path_nio = store_path / "nio"
store_path_megolm_backup = store_path / "megolm_backup"

store_path_next_batch = store_path / "next_batch.txt"

store_path.mkdir(parents=True, exist_ok=True)
store_path_nio.mkdir(parents=True, exist_ok=True)
if megolm_backup_passphrase:
    store_path_megolm_backup.mkdir(parents=True, exist_ok=True)
    if len(megolm_backup_passphrase) <= 10:
        Logger.warning(
            "matrix_megolm_backup_passphrase is too short. It is insecure."
        )
else:
    Logger.warning(
        "Matrix megolm backup is not setup. It is recommended to set matrix_megolm_backup_passphrase to a unique passphrase."
    )

if homeserver.endswith("/"):
    Logger.warning(
        "The matrix_homeserver ends with a slash(/), and this may cause M_UNRECOGNIZED error."
    )
homeserver_host = urllib3.util.parse_url(homeserver).host
matrix_bot: AsyncClient = AsyncClient(
    homeserver,
    user,
    store_path=store_path_nio,
    config=AsyncClientConfig(store_sync_tokens=True),
    proxy=proxy
)
matrix_bot.restore_login(user, device_id, token)
if matrix_bot.olm:
    Logger.info("Matrix E2E encryption support is available.")
else:
    Logger.info("Matrix E2E encryption support is not available.")
