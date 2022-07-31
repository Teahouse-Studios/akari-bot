from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from database.orm_base import Base

DB_LINK = Config('db_path')


class DBSession:
    def __init__(self):
        self.engine = engine = create_engine(DB_LINK)
        self.Session = sessionmaker()
        self.Session.configure(bind=self.engine)

    @property
    def session(self):
        return self.Session()

    def create(self):
        Base.metadata.create_all(bind=self.engine, checkfirst=True)


Session = DBSession()
