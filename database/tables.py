from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, text
from sqlalchemy.dialects.mysql import LONGTEXT

from database.orm_base import Base

from database.orm import Session

from config import Config


class EnabledModules(Base):
    """已打开的模块"""
    __tablename__ = "EnabledModules"
    targetId = Column(String(512), primary_key=True)
    enabledModules = Column(Text)


class SenderInfo(Base):
    """发送者信息"""
    __tablename__ = "SenderInfo"
    id = Column(String(512), primary_key=True)
    isInBlockList = Column(Boolean, default=False)
    isInAllowList = Column(Boolean, default=False)
    isSuperUser = Column(Boolean, default=False)
    warns = Column(Integer, default='0')
    disable_typing = Column(Boolean, default=False)


class StoredData(Base):
    """数据存储"""
    __tablename__ = "StoredData"
    name = Column(String(512), primary_key=True)
    value = Column(LONGTEXT if Config('db_path').startswith('mysql') else Text)


class TargetAdmin(Base):
    """所属赋予的管理员"""
    __tablename__ = "TargetAdmin"
    id = Column(Integer, primary_key=True)
    senderId = Column(String(512))
    targetId = Column(String(512))


class MuteList(Base):
    """禁言列表"""
    __tablename__ = "MuteList"
    targetId = Column(String(512), primary_key=True)


class CommandTriggerTime(Base):
    """命令触发时间"""
    __tablename__ = "CommandTriggerTime"
    targetId = Column(String(512), primary_key=True)
    commandName = Column(String(512))
    timestamp = Column(TIMESTAMP, default=text('CURRENT_TIMESTAMP'))


class GroupAllowList(Base):
    __tablename__ = "GroupAllowList"
    targetId = Column(String(512), primary_key=True)


class DBVersion(Base):
    __tablename__ = "DBVersion"
    value = Column(String(512), primary_key=True)


Session.create()
__all__ = ["EnabledModules", "TargetAdmin", "SenderInfo", "CommandTriggerTime", "GroupAllowList", "StoredData",
           "DBVersion"]
