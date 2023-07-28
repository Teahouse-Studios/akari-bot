from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.dialects.mysql import LONGTEXT
from database.orm import Session
from database.orm_base import Base

db = Session
session = db.session
engine = db.engine


class Caves(Base):
    """
    储存回声洞数据
    -------------
    """
    __tablename__ = "module_cave_CavesInfo"
    __table_args__ = {"extend_existing": True}
    Id = Column(Integer, primary_key=True)
    sender = Column(LONGTEXT if session.bind.dialect.name == "mysql" else Text)
    content = Column(LONGTEXT if session.bind.dialect.name == "mysql" else Text)


Session.create()
