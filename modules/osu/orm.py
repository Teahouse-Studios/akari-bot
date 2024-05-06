from sqlalchemy import Column, String

from database.orm import Session
from database.orm_base import Base

table_prefix = 'module_osu_'
db = Session
session = db.session
engine = db.engine


class OsuBindInfo(Base):
    __tablename__ = table_prefix + 'OsuBindInfo'
    __table_args__ = {'extend_existing': True}
    targetId = Column(String(512), primary_key=True)
    username = Column(String(512))