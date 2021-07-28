from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .tables import Base
from config import Config


DB_LINK = Config('db_path')

engine = create_engine(DB_LINK)

Base.metadata.create_all(bind=engine, checkfirst=True)

session = sessionmaker(engine)()

