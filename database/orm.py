from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Config
from database.tables import *

DB_LINK = Config('db_path')

engine = create_engine(DB_LINK)

Base.metadata.create_all(bind=engine, checkfirst=True)

session = sessionmaker(engine)()
