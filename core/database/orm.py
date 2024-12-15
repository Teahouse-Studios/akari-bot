import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from core.config import Config
from core.constants.default import db_path_default
from core.constants.path import database_path
from core.database.orm_base import Base

DB_LINK = Config("db_path", default=db_path_default, secret=True)

db_path = database_path
if DB_LINK.startswith("sqlite:///"):
    db_path = os.path.dirname(DB_LINK.replace("sqlite:///", ""))
os.makedirs(db_path, exist_ok=True)


class DBSession:
    def __init__(self):
        self.engine = create_engine(
            DB_LINK, isolation_level="READ UNCOMMITTED", pool_pre_ping=True
        )
        self.Session = sessionmaker()
        self.Session.configure(bind=self.engine)

    @property
    def session(self):
        return self.Session()

    def create(self):
        Base.metadata.create_all(bind=self.engine, checkfirst=True)


class AsyncDBSession:
    def __init__(self):
        self.engine = create_async_engine(DB_LINK, isolation_level="READ UNCOMMITTED")
        self.Session = async_sessionmaker()
        self.Session.configure(bind=self.engine)

    async def session(self):
        return self.Session()

    def create(self):
        Base.metadata.create_all(bind=self.engine, checkfirst=True)


Session = DBSession()
