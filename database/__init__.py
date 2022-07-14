import datetime
import ujson as json
from typing import Union

from tenacity import retry, stop_after_attempt

from config import Config
from core.elements.message import MessageSession, FetchTarget, FetchedSession
from core.elements.temp import EnabledModulesCache, SenderInfoCache
from database.orm import Session
from database.tables import *
from database.tables import AnalyticsData

cache = Config('db_cache')


class Dict2Object(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


session = Session.session


def auto_rollback_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            session.rollback()
            raise e

    return wrapper


class BotDBUtil:
    database_version = 1

    class Module:
        @retry(stop=stop_after_attempt(3))
        def __init__(self, msg: [MessageSession, str]):
            if isinstance(msg, MessageSession):
                self.targetId = str(msg.target.targetId)
            else:
                self.targetId = msg
            self.need_insert = False
            self.enable_modules_list = EnabledModulesCache.get_cache(self.targetId) if cache else False
            if not self.enable_modules_list:
                query = self.query_EnabledModules
                if query is None:
                    self.need_insert = True
                    self.enable_modules_list = []
                else:
                    query_ = query.enabledModules
                    self.enable_modules_list = json.loads(query_)
                if cache:
                    EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)

        @property
        @auto_rollback_error
        def query_EnabledModules(self):
            return session.query(EnabledModules).filter_by(targetId=self.targetId).first()

        def check_target_enabled_module_list(self) -> list:
            return self.enable_modules_list

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enable_modules_list else False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def enable(self, module_name) -> bool:
            if isinstance(module_name, str):
                if module_name not in self.enable_modules_list:
                    self.enable_modules_list.append(module_name)
            elif isinstance(module_name, (list, tuple)):
                for x in module_name:
                    if x not in self.enable_modules_list:
                        self.enable_modules_list.append(x)
            value = json.dumps(self.enable_modules_list)
            if self.need_insert:
                table = EnabledModules(targetId=self.targetId,
                                       enabledModules=value)
                session.add_all([table])
            else:
                self.query_EnabledModules.enabledModules = value
            session.commit()
            session.expire_all()
            if cache:
                EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def disable(self, module_name) -> bool:
            if isinstance(module_name, str):
                if module_name in self.enable_modules_list:
                    self.enable_modules_list.remove(module_name)
            elif isinstance(module_name, (list, tuple)):
                for x in module_name:
                    if x in self.enable_modules_list:
                        self.enable_modules_list.remove(x)
            if not self.need_insert:
                self.query_EnabledModules.enabledModules = json.dumps(self.enable_modules_list)
                session.commit()
                session.expire_all()
                if cache:
                    EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)
            return True

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def get_enabled_this(module_name):
            query = session.query(EnabledModules).filter(EnabledModules.enabledModules.like(f'%{module_name}%'))
            targetIds = []
            for x in query:
                enabled_list = json.loads(x.enabledModules)
                if module_name in enabled_list:
                    targetIds.append(x.targetId)
            return targetIds

    class SenderInfo:
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def __init__(self, senderId):
            self.senderId = senderId
            query_cache = SenderInfoCache.get_cache(self.senderId) if cache else False
            if query_cache:
                self.query = Dict2Object(query_cache)
            else:
                self.query = self.query_SenderInfo
                if self.query is None:
                    session.add_all([SenderInfo(id=senderId)])
                    session.commit()
                    self.query = session.query(SenderInfo).filter_by(id=senderId).first()
                if cache:
                    SenderInfoCache.add_cache(self.senderId, self.query.__dict__)

        @property
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def query_SenderInfo(self):
            return session.query(SenderInfo).filter_by(id=self.senderId).first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit(self, column: str, value):
            query = self.query_SenderInfo
            setattr(query, column, value)
            session.commit()
            session.expire_all()
            if cache:
                SenderInfoCache.add_cache(self.senderId, query.__dict__)
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def check_TargetAdmin(self, targetId):
            query = session.query(TargetAdmin).filter_by(senderId=self.senderId, targetId=targetId).first()
            if query is not None:
                return query
            return False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add_TargetAdmin(self, targetId):
            if not self.check_TargetAdmin(targetId):
                session.add_all([TargetAdmin(senderId=self.senderId, targetId=targetId)])
                session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove_TargetAdmin(self, targetId):
            query = self.check_TargetAdmin(targetId)
            if query:
                session.delete(query)
                session.commit()
            return True

    class CoolDown:
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def __init__(self, msg: MessageSession, name):
            self.msg = msg
            self.name = name
            self.query = session.query(CommandTriggerTime).filter_by(targetId=str(msg.target.senderId),
                                                                     commandName=name).first()
            self.need_insert = True if self.query is None else False

        def check(self, delay):
            if not self.need_insert:
                now = datetime.datetime.now().timestamp() - self.query.timestamp.timestamp()
                if now > delay:
                    return 0
                return now
            return 0

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def reset(self):
            if not self.need_insert:
                session.delete(self.query)
                session.commit()
            session.add_all([CommandTriggerTime(targetId=self.msg.target.senderId, commandName=self.name)])
            session.commit()

    @staticmethod
    @retry(stop=stop_after_attempt(3))
    @auto_rollback_error
    def isGroupInAllowList(targetId):
        session.expire_all()
        query = session.query(GroupAllowList).filter_by(targetId=targetId).first()
        if query is not None:
            return True
        return False

    class Muting:
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def __init__(self, msg: MessageSession):
            self.msg = msg
            self.targetId = msg.target.targetId
            self.query = session.query(MuteList).filter_by(targetId=self.targetId).first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def check(self):
            if self.query is not None:
                return True
            return False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(self):
            session.add(MuteList(targetId=self.targetId))
            session.commit()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove(self):
            if self.query is not None:
                session.delete(self.query)
                session.commit()

    class Data:
        def __init__(self, msg: Union[MessageSession, FetchTarget]):
            self.targetName = msg.target.clientName if isinstance(msg, MessageSession) else msg.name

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(self, name, value: str):
            session.add(StoredData(name=f'{self.targetName}|{name}', value=value))
            session.commit()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def get(self, name):
            return session.query(StoredData).filter_by(name=f'{self.targetName}|{name}').first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def update(self, name, value: str):
            exists = self.get(name)
            if exists is None:
                self.add(name=name, value=value)
            else:
                exists.value = value
                session.commit()
            return True

    class Options:
        def __init__(self, msg: Union[MessageSession, FetchTarget, str]):
            self.targetId = msg.target.targetId if isinstance(msg, (MessageSession, FetchTarget)) else msg

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit(self, k, v):
            get_ = session.query(TargetOptions).filter_by(targetId=self.targetId).first()
            if get_ is None:
                session.add_all([TargetOptions(targetId=self.targetId, options=json.dumps({k: v}))])
            else:
                get_.options = json.dumps({**json.loads(get_.options), k: v})
            session.commit()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def get(self, k=None):
            query = session.query(TargetOptions).filter_by(targetId=self.targetId).first()
            if query is None:
                return {}
            value: dict = json.loads(query.options)
            if k is None:
                return value
            else:
                return value.get(k)

    class Analytics:
        def __init__(self, target: Union[MessageSession, FetchedSession]):
            self.target = target

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(self, command, module_name, module_type):
            session.add(AnalyticsData(targetId=self.target.target.targetId,
                                      senderId=self.target.target.senderId,
                                      command=command,
                                      moduleName=module_name, moduleType=module_type))
            session.commit()

        @staticmethod
        def get_count():
            return session.query(AnalyticsData).count()

        @staticmethod
        def get_first():
            return session.query(AnalyticsData).filter_by(id=1).first()


__all__ = ["BotDBUtil", "auto_rollback_error", "session"]
