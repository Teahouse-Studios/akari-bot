from pathlib import Path

from core.config import Config
from core.constants import db_path_default, database_path

db_link = Config("db_path", default=db_path_default, secret=True)
db_type = db_link.split("://")[0].split("+")[0]
db_path = database_path

if db_type == "sqlite":
    db_path = Path(db_link.replace("sqlite://", "")).parent
db_path.mkdir(parents=True, exist_ok=True)


def get_db_link():
    return f"{db_type}://{db_link.split("://")[1]}"
