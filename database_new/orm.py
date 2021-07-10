from sqlalchemy import create_engine
from database_new.tables import *


DB_LINK = 'sqlite:///database_new/save.db'

engine = create_engine(DB_LINK)

Base.metadata.create_all(bind=engine, checkfirst=True)
