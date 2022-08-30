import datetime
from typing import Union, List

import ujson as json
from tenacity import retry, stop_after_attempt

from core.elements.message import MessageSession, FetchTarget, FetchedSession
from database.orm import Session
from database.tables import *
from database.tables import TargetInfo

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
    database_version = 2

    class TargetInfo:
        def __init__(self, msg: [MessageSession, FetchTarget, str]):
            if isinstance(msg, (MessageSession, FetchTarget)):
                self.targetId = str(msg.target.targetId)
            else:
                self.targetId = msg
            self.query = self.query_data

        @property
        def query_data(self):
            return session.query(TargetInfo).filter_by(targetId=self.targetId).first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def init(self):
            if self.query is None:
                session.add_all([TargetInfo(targetId=self.targetId)])
                session.commit()
                return self.query_data
            else:
                return self.query

        @property
        def enabled_modules(self) -> list:
            if self.query is None:
                return []
            return json.loads(self.query.enabledModules)

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enabled_modules else False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def enable(self, module_name) -> bool:
            if self.query is None:
                self.query = self.init()
            enabled_modules = self.enabled_modules.copy()
            if isinstance(module_name, str):
                if module_name not in enabled_modules:
                    enabled_modules.append(module_name)
            elif isinstance(module_name, (list, tuple)):
                for x in module_name:
                    if x not in enabled_modules:
                        enabled_modules.append(x)
            self.query.enabledModules = json.dumps(enabled_modules)
            session.commit()
            session.expire_all()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def disable(self, module_name) -> bool:
            if self.query is not None:
                enabled_modules = self.enabled_modules.copy()
                if isinstance(module_name, str):
                    if module_name in enabled_modules:
                        enabled_modules.remove(module_name)
                elif isinstance(module_name, (list, tuple)):
                    for x in module_name:
                        if x in enabled_modules:
                            enabled_modules.remove(x)
                self.query.enabledModules = json.dumps(enabled_modules)
                session.commit()
                session.expire_all()
            return True

        @property
        def is_muted(self):
            if self.query is None:
                return False
            return self.query.muted

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def switch_mute(self) -> bool:
            if self.query is None:
                self.query = self.init()
            self.query.muted = not self.query.muted
            session.commit()
            return self.query.muted

        @property
        def options(self):
            if self.query is None:
                return {}
            return json.loads(self.query.options)

        def get_option(self, k=None):
            if self.query is None and k is None:
                return {}
            elif self.query is None and k is not None:
                return None
            if k is None:
                return self.options
            else:
                return self.options.get(k)

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit_option(self, k, v) -> bool:
            if self.query is None:
                self.query = self.init()
            self.query.options = json.dumps({**json.loads(self.query.options), k: v})
            session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove_option(self, k) -> bool:
            if self.query is not None:
                options = self.options.copy()
                if k in options:
                    options.pop(k)
                self.query.options = options
                session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit(self, column: str, value):
            if self.query is None:
                self.query = self.init()
            query = self.query
            setattr(query, column, value)
            session.commit()
            session.expire_all()
            return True

        @property
        def custom_admins(self):
            if self.query is None:
                return []
            return json.loads(self.query.custom_admins)

        def check_custom_target_admin(self, sender_id) -> bool:
            return sender_id in self.custom_admins

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add_custom_admin(self, sender_id) -> bool:
            if self.query is None:
                self.query = self.init()
            custom_admins = self.custom_admins.copy()
            if sender_id not in custom_admins:
                custom_admins.append(sender_id)
            self.query.custom_admins = json.dumps(custom_admins)
            session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove_custom_admin(self, sender_id) -> bool:
            if self.query is not None:
                custom_admins = self.custom_admins.copy()
                if sender_id in custom_admins:
                    custom_admins.remove(sender_id)
                self.query.custom_admins = json.dumps(custom_admins)
            return True

        @property
        def locale(self):
            if self.query is None:
                self.query = self.init()
            return self.query.locale

        @staticmethod
        def get_enabled_this(module_name, id_prefix=None) -> List[TargetInfo]:
            filter_ = [TargetInfo.enabledModules.like(f'%"{module_name}"%')]
            if id_prefix is not None:
                filter_.append(TargetInfo.targetId.like(f'{id_prefix}%'))
            return session.query(TargetInfo).filter(*filter_).all()

    class SenderInfo:
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def __init__(self, senderId):
            self.senderId = senderId
            self.query = self.query_SenderInfo
            if self.query is None:
                session.add_all([SenderInfo(id=senderId)])
                session.commit()
                self.query = session.query(SenderInfo).filter_by(id=senderId).first()

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

        @staticmethod
        def get_data_by_times(new, old, module_name=None):
            filter_ = [AnalyticsData.timestamp <= new, AnalyticsData.timestamp >= old]
            if module_name is not None:
                filter_.append(AnalyticsData.moduleName == module_name)
            return session.query(AnalyticsData).filter(*filter_).all()

        @staticmethod
        def get_count_by_times(new, old, module_name=None):
            filter_ = [AnalyticsData.timestamp < new, AnalyticsData.timestamp > old]
            if module_name is not None:
                filter_.append(AnalyticsData.moduleName == module_name)
            return session.query(AnalyticsData).filter(*filter_).count()

    class UnfriendlyActions:
        def __init__(self, targetId, senderId):
            self.targetId = targetId
            self.senderId = senderId

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def check_mute(self) -> bool:
            """

            :return: True = yes, False = no
            """
            query = session.query(UnfriendlyActionsTable).filter_by(targetId=self.targetId).all()
            unfriendly_list = []
            for records in query:
                if datetime.datetime.now().timestamp() - records.timestamp.timestamp() < 432000:
                    unfriendly_list.append(records)
            if len(unfriendly_list) > 5:
                return True
            count = {}
            for criminal in unfriendly_list:
                if datetime.datetime.now().timestamp() - criminal.timestamp.timestamp() < 86400:
                    if criminal.senderId not in count:
                        count[criminal.senderId] = 0
                    else:
                        count[criminal.senderId] += 1
            if len(count) >= 3:
                return True
            for convict in count:
                if count[convict] >= 3:
                    return True
            return False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add_and_check(self, action='default', detail='') -> bool:
            """

            :return: True = yes, False = no
            """
            session.add_all(
                [UnfriendlyActionsTable(targetId=self.targetId, senderId=self.senderId, action=action, detail=detail)])
            session.commit()
            return self.check_mute()


__all__ = ["BotDBUtil", "auto_rollback_error", "session"]
