import importlib
import os
from sqlalchemy import Column, Integer, String, Text, Time, TIMESTAMP, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
import datetime

from core.logger import Logger

Base = declarative_base()


class EnabledModules(Base):
    """已打开的模块"""
    __tablename__ = "EnabledModules"
    targetId = Column(String(512), primary_key=True)
    enabledModules = Column(Text)


class SenderInfo(Base):
    """发送者信息"""
    __tablename__ = "SenderInfo"
    id = Column(String(512), primary_key=True)
    isInBlackList = Column(Boolean, default=False)
    isInWhiteList = Column(Boolean, default=False)
    isSuperUser = Column(Boolean, default=False)
    warns = Column(Integer, default='0')


class TargetAdmin(Base):
    """所属赋予的管理员"""
    __tablename__ = "TargetAdmin"
    id = Column(Integer, primary_key=True)
    senderId = Column(String(512))
    targetId = Column(String(512))


class CommandTriggerTime(Base):
    """命令触发时间"""
    __tablename__ = "CommandTriggerTime"
    targetId = Column(String(512), primary_key=True)
    commandName = Column(String(512))
    timestamp = Column(TIMESTAMP, default=text('CURRENT_TIMESTAMP'))


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

