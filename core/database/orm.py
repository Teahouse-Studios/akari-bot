from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from core.database.link import db_link
from core.database.orm_base import Base


class DBSession:
    def __init__(self):
        self.engine = create_engine(
            db_link, isolation_level="READ UNCOMMITTED", pool_pre_ping=True
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
        self.engine = create_async_engine(db_link, isolation_level="READ UNCOMMITTED")
        self.Session = async_sessionmaker()
        self.Session.configure(bind=self.engine)

    async def session(self):
        return self.Session()

    def create(self):
        Base.metadata.create_all(bind=self.engine, checkfirst=True)


Session = DBSession()
