from sqlalchemy import Column, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.declarative import declarative_base

from database.orm import DBSession

Base = declarative_base()
table_prefix = 'module_cytoid_'
db = DBSession()
session = db.session
engine = db.engine


class CytoidBindInfo(Base):
    __tablename__ = table_prefix + 'CytoidBindInfo'
    targetId = Column(String(512), primary_key=True)
    username = Column(String(512))


Base.metadata.create_all(bind=engine, checkfirst=True)
