import os

from core.config import Config
from core.constants import db_path_default, database_path

db_link = Config("db_path", default=db_path_default, secret=True)
db_type = db_link.split("://")[0].split("+")[0]
db_path = database_path

if db_type == "sqlite":
    # 兼容 SQLAlchemy 格式 SQLite 连接串
    absolute = False
    if db_link.startswith("sqlite:////"):
        db_link = db_link.replace("sqlite:////", "sqlite:///")
        absolute = True
    if db_link.startswith("sqlite:///") and not absolute:
        db_link = db_link.replace("sqlite:///", "sqlite://")

    db_path = os.path.dirname(db_link.replace("sqlite://", ""))
os.makedirs(db_path, exist_ok=True)


def get_db_link():
    return f"{db_type}://{db_link.split("://")[1]}"
