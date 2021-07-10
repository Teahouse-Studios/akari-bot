from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.tables import *


DB_LINK = 'sqlite:///database/save.db'

engine = create_engine(DB_LINK)

Base.metadata.create_all(bind=engine, checkfirst=True)

session = sessionmaker(engine)()

