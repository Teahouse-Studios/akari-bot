import datetime

from core.elements.message import MessageSession
from core.elements.temp import EnabledModulesCache, SenderInfoCache
from database.orm import DBSession
from database.tables import EnabledModules, SenderInfo, TargetAdmin, CommandTriggerTime


def convert_list_to_str(lst: list) -> str:
    return '|'.join(lst)


def convert_str_to_list(s: str) -> list:
    return s.split('|')


class Dict2Object(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


session = DBSession().session


class BotDBUtil:
    class Module:
        def __init__(self, msg: [MessageSession, str]):
            if isinstance(msg, MessageSession):
                self.targetId = str(msg.target.targetId)
            else:
                self.targetId = msg
            self.need_insert = False
            self.enable_modules_list = EnabledModulesCache.get_cache(self.targetId)
            if not self.enable_modules_list:
                query = self.query_EnabledModules
                if query is None:
                    self.need_insert = True
                    self.enable_modules_list = []
                else:
                    query_ = query.enabledModules
                    self.enable_modules_list = convert_str_to_list(query_)
                EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)

        @property
        def query_EnabledModules(self):
            return session.query(EnabledModules).filter_by(targetId=self.targetId).first()

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enable_modules_list else False

        def enable(self, module_name) -> bool:
            if isinstance(module_name, str):
                if module_name not in self.enable_modules_list:
                    self.enable_modules_list.append(module_name)
            elif isinstance(module_name, (list, tuple)):
                for x in module_name:
                    if x not in self.enable_modules_list:
                        self.enable_modules_list.append(x)
            value = convert_list_to_str(self.enable_modules_list)
            if self.need_insert:
                table = EnabledModules(targetId=self.targetId,
                                       enabledModules=value)
                session.add_all([table])
            else:
                self.query_EnabledModules.enabledModules = value
            session.commit()
            session.expire_all()
            EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)
            return True

        def disable(self, module_name) -> bool:
            if isinstance(module_name, str):
                if module_name in self.enable_modules_list:
                    self.enable_modules_list.remove(module_name)
            elif isinstance(module_name, (list, tuple)):
                for x in module_name:
                    if x in self.enable_modules_list:
                        self.enable_modules_list.remove(x)
            if not self.need_insert:
                self.query_EnabledModules.enabledModules = convert_list_to_str(self.enable_modules_list)
                session.commit()
                session.expire_all()
                EnabledModulesCache.add_cache(self.targetId, self.enable_modules_list)
            return True

        @staticmethod
        def get_enabled_this(module_name):
            query = session.query(EnabledModules).filter(EnabledModules.enabledModules.like(f'%{module_name}%'))
            targetIds = []
            for x in query:
                enabled_list = convert_str_to_list(x.enabledModules)
                if module_name in enabled_list:
                    targetIds.append(x.targetId)
            return targetIds

    class SenderInfo:
        def __init__(self, senderId):
            self.senderId = senderId
            query_cache = SenderInfoCache.get_cache(self.senderId)
            if query_cache:
                self.query = Dict2Object(query_cache)
            else:
                self.query = self.query_SenderInfo
                if self.query is None:
                    session.add_all([SenderInfo(id=senderId)])
                    session.commit()
                    self.query = session.query(SenderInfo).filter_by(id=senderId).first()
                SenderInfoCache.add_cache(self.senderId, self.query.__dict__)

        @property
        def query_SenderInfo(self):
            return session.query(SenderInfo).filter_by(id=self.senderId).first()

        def edit(self, column: str, value):
            query = self.query_SenderInfo
            setattr(query, column, value)
            session.commit()
            session.expire_all()
            SenderInfoCache.add_cache(self.senderId, query.__dict__)
            return True

        def check_TargetAdmin(self, targetId):
            query = session.query(TargetAdmin).filter_by(senderId=self.senderId, targetId=targetId).first()
            if query is not None:
                return query
            return False

        def add_TargetAdmin(self, targetId):
            if not self.check_TargetAdmin(targetId):
                session.add_all([TargetAdmin(senderId=self.senderId, targetId=targetId)])
                session.commit()
            return True

        def remove_TargetAdmin(self, targetId):
            query = self.check_TargetAdmin(targetId)
            if query:
                session.delete(query)
                session.commit()

    class CoolDown:
        def __init__(self, msg: MessageSession, name):
            self.msg = msg
            self.name = name
            self.query = session.query(CommandTriggerTime).filter_by(targetId=str(msg.target.targetId),
                                                                     commandName=name).first()
            self.need_insert = True if self.query is None else False

        def check(self, delay):
            if not self.need_insert:
                now = datetime.datetime.now().timestamp() - self.query.timestamp.timestamp()
                if now > delay:
                    return 0
                return now
            return 0

        def reset(self):
            if not self.need_insert:
                session.delete(self.query)
                session.commit()
            session.add_all([CommandTriggerTime(targetId=self.msg.target.targetId, commandName=self.name)])
            session.commit()
