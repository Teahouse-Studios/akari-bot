from sqlalchemy import Column, String

from database.orm import Session
from database.orm_base import Base

table_prefix = 'module_arcaea_'
db = Session
session = db.session
engine = db.engine


class ArcBindInfo(Base):
    __tablename__ = table_prefix + 'ArcBindInfo'
    targetId = Column(String(512), primary_key=True)
    username = Column(String(512))
    friendcode = Column(String(512))


Session.create()
