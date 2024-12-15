from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, text
from sqlalchemy.dialects.mysql import LONGTEXT

from core.config import Config
from core.database.orm import Session, DB_LINK
from core.database.orm_base import Base

is_mysql = DB_LINK.startswith("mysql")
default_locale = Config("default_locale", cfg_type=str)


class SenderInfo(Base):
    """发送者信息"""

    __tablename__ = "SenderInfo"
    id = Column(String(512), primary_key=True)
    isInBlockList = Column(Boolean, default=False)
    isInAllowList = Column(Boolean, default=False)
    isSuperUser = Column(Boolean, default=False)
    warns = Column(Integer, default=0)
    disableTyping = Column(Boolean, default=False)
    petal = Column(Integer, default=0)
    __table_args__ = {"mysql_charset": "utf8mb4"}


class TargetInfoTable(Base):
    __tablename__ = "TargetInfo"
    targetId = Column(String(512), primary_key=True)
    enabledModules = Column(LONGTEXT if is_mysql else Text, default="[]")
    options = Column(LONGTEXT if is_mysql else Text, default="{}")
    customAdmins = Column(LONGTEXT if is_mysql else Text, default="[]")
    muted = Column(Boolean, default=False)
    locale = Column(String(512), default=default_locale)
    __table_args__ = {"mysql_charset": "utf8mb4"}


class StoredData(Base):
    """数据存储"""

    __tablename__ = "StoredData"
    name = Column(String(512), primary_key=True)
    value = Column(LONGTEXT if is_mysql else Text)
    __table_args__ = {"mysql_charset": "utf8mb4"}


class CommandTriggerTime(Base):
    """命令触发时间"""

    __tablename__ = "CommandTriggerTime"
    targetId = Column(String(512), primary_key=True)
    commandName = Column(String(512))
    timestamp = Column(TIMESTAMP, default=text("CURRENT_TIMESTAMP"))
    __table_args__ = {"mysql_charset": "utf8mb4"}


class GroupBlockList(Base):
    __tablename__ = "GroupBlockList"
    targetId = Column(String(512), primary_key=True)
    __table_args__ = {"mysql_charset": "utf8mb4"}


class AnalyticsData(Base):
    """统计信息"""

    __tablename__ = "Analytics"
    id = Column(Integer, primary_key=True)
    moduleName = Column(String(512))
    moduleType = Column(String(512))
    targetId = Column(String(512))
    senderId = Column(String(512))
    command = Column(LONGTEXT if is_mysql else Text)
    timestamp = Column(TIMESTAMP, default=text("CURRENT_TIMESTAMP"))

    __table_args__ = {"mysql_charset": "utf8mb4"}


class DBVersion(Base):
    __tablename__ = "DBVersion"
    value = Column(String(512), primary_key=True)
    __table_args__ = {"mysql_charset": "utf8mb4"}


class UnfriendlyActionsTable(Base):
    __tablename__ = "unfriendly_action"
    id = Column(Integer, primary_key=True)
    targetId = Column(String(512))
    senderId = Column(String(512))
    action = Column(String(512))
    detail = Column(String(512))
    timestamp = Column(TIMESTAMP, default=text("CURRENT_TIMESTAMP"))
    __table_args__ = {"mysql_charset": "utf8mb4"}


class JobQueueTable(Base):
    __tablename__ = "job_queues"
    taskid = Column(String(512), primary_key=True)
    targetClient = Column(String(512))
    hasDone = Column(Boolean, default=False)
    action = Column(String(512))
    args = Column(LONGTEXT if is_mysql else Text, default="{}")
    returnVal = Column(LONGTEXT if is_mysql else Text, default="{}")
    timestamp = Column(TIMESTAMP, default=text("CURRENT_TIMESTAMP"))

    __table_args__ = {"mysql_charset": "utf8mb4"}


Session.create()
__all__ = [
    "SenderInfo",
    "TargetInfoTable",
    "CommandTriggerTime",
    "GroupBlockList",
    "StoredData",
    "DBVersion",
    "AnalyticsData",
    "UnfriendlyActionsTable",
    "JobQueueTable",
]
