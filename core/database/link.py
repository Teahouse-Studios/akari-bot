import os

from core.config import Config
from core.constants import db_path_default, database_path

db_link = Config("db_path", default=db_path_default, secret=True)
db_path = database_path

db_type = db_link.split("://")[0].split("+")[0]
if db_type == "sqlite":
    db_path = os.path.dirname(db_link.replace("sqlite:///", ""))
os.makedirs(db_path, exist_ok=True)


def get_db_link(orm_type="sqlalchemy"):
    if orm_type == "sqlalchemy":
        return db_link
    if orm_type == "tortoise":
        return db_type + "://" + db_link.split("://")[1]
