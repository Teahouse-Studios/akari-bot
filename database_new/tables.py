from sqlalchemy import Column, Integer, String, Text, Time, TIMESTAMP
from sqlalchemy.orm import sessionmaker
from . import orm

session = sessionmaker(orm.engine)
Base = orm.Base

class GroupEnabledModules(Base):
    """群内已打开的模块"""
    __tablename__ = "GroupEnabledModules"
    TargetId = Column(String(512), primary_key=True)
    EnabledModules = Column(Text)


class FriendEnabledModules(Base):
    """好友已打开的模块"""
    __tablename__ = "FriendEnabledModules"
    TargetId = Column(String(512), primary_key=True)
    EnabledModules = Column(Text)


class BlackList(Base):
    """黑名单"""
    __tablename__ = "BlackList"
    TargetId = Column(String(512), primary_key=True)


class WhiteList(Base):
    """黑名单"""
    __tablename__ = "WhiteList"
    TargetId = Column(String(512), primary_key=True)


class WarnList(Base):
    """警告列表"""
    __tablename__ = "WarnList"
    TargetId = Column(String(512), primary_key=True)


class SuperUser(Base):
    """Bot管理员"""
    __tablename__ = "SuperUser"
    TargetId = Column(String(512), primary_key=True)


class CommandTriggerTime(Base):
    """命令触发时间"""
    __tablename__ = "CommandTriggerTime"
    TargetId = Column(String(512), primary_key=True)
    CommandName = Column(TIMESTAMP, nullable=False)
