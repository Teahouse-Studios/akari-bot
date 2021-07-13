import importlib
import os
from sqlalchemy import Column, Integer, String, Text, Time, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

from core.logger import Logger

Base = declarative_base()


class EnabledModules(Base):
    """已打开的模块"""
    __tablename__ = "EnabledModules"
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
    Frequency = Column(Integer)


class SuperUser(Base):
    """Bot管理员"""
    __tablename__ = "SuperUser"
    TargetId = Column(String(512), primary_key=True)


class FromAdmin(Base):
    """所属赋予的管理员"""
    __tablename__ = "FromAdmin"
    TargetId = Column(String(512), primary_key=True)
    FromId = Column(String(512))


class CommandTriggerTime(Base):
    """命令触发时间"""
    __tablename__ = "CommandTriggerTime"
    TargetId = Column(String(512), primary_key=True)
    CommandName = Column(TIMESTAMP, nullable=False)


load_dir_path = os.path.abspath('./modules/')
dir_list = os.listdir(load_dir_path)
fun_file = None
for file_name in dir_list:
    file_path = f'{load_dir_path}/{file_name}'
    fun_file = None
    if os.path.isdir(file_path):
        if file_name != '__pycache__':
            tablesfile = f'{file_path}/tables.py'
            if os.path.exists(tablesfile):
                fun_file = f'{file_name}'
    if fun_file is not None:
        Logger.info(f'Loading modules.{fun_file}...')
        modules = f'modules.{fun_file}.tables'
        i = importlib.import_module(modules)

