from sqlalchemy import Column, String, Text

from database.tables import Base


class QAQ(Base):
    """已打开的模块"""
    __tablename__ = "QAQz01d"
    TargetId = Column(String(512), primary_key=True)
    EnabledModules = Column(Text)