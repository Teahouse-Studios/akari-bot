from pathlib import Path

from core.config.base import CoreSecretConfig
from core.constants import database_path

db_link = CoreSecretConfig.db_path
db_parts = db_link.split("://")
db_type = db_parts[0].split("+")[0] if db_parts else "sqlite"
db_path = database_path

if db_type == "sqlite":
    db_path = Path(db_link.replace("sqlite://", "")).parent
db_path.mkdir(parents=True, exist_ok=True)


def get_db_link():
    parts = db_link.split("://", 1)
    return f"{db_type}://{parts[1]}" if len(parts) > 1 else db_link
