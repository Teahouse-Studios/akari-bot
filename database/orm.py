from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.tables import *


DB_LINK = "mysql+pymysql://root:WUyou2004517@localhost:3306/bot"

engine = create_engine(DB_LINK)

Base.metadata.create_all(bind=engine, checkfirst=True)

session = sessionmaker(engine)()

