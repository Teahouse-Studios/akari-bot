from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT

from core.database.orm import Session
from core.database.orm_base import Base

table_prefix = "module_wikilog_"
db = Session
session = db.session
engine = db.engine


class WikiLogTargetSetInfo(Base):
    __tablename__ = table_prefix + "WikiLogTargetSetInfo"
    __table_args__ = {"extend_existing": True, "mysql_charset": "utf8mb4"}
    targetId = Column(String(512), primary_key=True)
    infos = Column(LONGTEXT if session.bind.dialect.name == "mysql" else Text)


Session.create()
