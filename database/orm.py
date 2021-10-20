from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from database.tables import *

DB_LINK = Config('db_path')


class DBSession:
    def __init__(self):
        self.engine = engine = create_engine(DB_LINK)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        self.Session = sessionmaker()
        self.Session.configure(bind=self.engine)

    @property
    def session(self):
        return self.Session()
