import datetime
import uuid
from typing import Union, List

import ujson as json
from tenacity import retry, stop_after_attempt

from core.types.message import MessageSession, FetchTarget, FetchedSession
from database.orm import Session
from database.tables import *

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
    database_version = 3

    class TargetInfo:
        def __init__(self, msg: Union[MessageSession, FetchTarget, str]):
            if isinstance(msg, (MessageSession, FetchTarget)):
                self.target_id = str(msg.target.target_id)
            else:
                self.target_id = msg
            self.query = self.query_data

        @property
        def query_data(self):
            return session.query(TargetInfo).filter_by(targetId=self.target_id).first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def init(self):
            if not self.query:
                session.add_all([TargetInfo(targetId=self.target_id)])
                session.commit()
                return self.query_data
            else:
                return self.query

        @property
        def enabled_modules(self) -> list:
            if not self.query:
                return []
            return json.loads(self.query.enabledModules)

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enabled_modules else False

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def enable(self, module_name) -> bool:
            if not self.query:
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
            if self.query:
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
            if not self.query:
                return False
            return self.query.muted

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def switch_mute(self) -> bool:
            if not self.query:
                self.query = self.init()
            self.query.muted = not self.query.muted
            session.commit()
            return self.query.muted

        @property
        def options(self) -> dict:
            if not self.query:
                return {}
            return json.loads(self.query.options)

        def get_option(self, k=None):
            if not self.query and not k:
                return {}
            elif not self.query and k:
                return None
            if not k:
                return self.options
            else:
                return self.options.get(k)

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit_option(self, k, v) -> bool:
            if not self.query:
                self.query = self.init()
            self.query.options = json.dumps({**json.loads(self.query.options), k: v})
            session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove_option(self, k) -> bool:
            if self.query:
                options = self.options.copy()
                if k in options:
                    options.pop(k)
                options = json.dumps(options)
                self.query.options = options
                session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit(self, column: str, value):
            if not self.query:
                self.query = self.init()
            query = self.query
            setattr(query, column, value)
            session.commit()
            session.expire_all()
            return True

        @property
        def custom_admins(self):
            if not self.query:
                return []
            return json.loads(self.query.custom_admins)

        def check_custom_target_admin(self, sender_id) -> bool:
            return sender_id in self.custom_admins

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add_custom_admin(self, sender_id) -> bool:
            if not self.query:
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
            if self.query:
                custom_admins = self.custom_admins.copy()
                if sender_id in custom_admins:
                    custom_admins.remove(sender_id)
                self.query.custom_admins = json.dumps(custom_admins)
            return True

        @property
        def locale(self):
            if not self.query:
                self.query = self.init()
            return self.query.locale

        @staticmethod
        def get_enabled_this(module_name, id_prefix=None) -> List[TargetInfo]:
            filter_ = [TargetInfo.enabledModules.like(f'%"{module_name}"%')]
            if id_prefix:
                filter_.append(TargetInfo.targetId.like(f'{id_prefix}%'))
            return session.query(TargetInfo).filter(*filter_).all()

        @property
        def petal(self):
            if not self.query:
                return 0
            return self.query.petal

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def modify_petal(self, amount: int) -> bool:
            if not self.query:
                self.query = self.init()
            petal = self.petal
            new_petal = petal + amount
            self.query.petal = new_petal
            session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def clear_petal(self) -> bool:
            if not self.query:
                self.query = self.init()
            self.query.petal = 0
            session.commit()
            return True

    class SenderInfo:
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def __init__(self, sender_id):
            self.sender_id = sender_id
            self.query = self.query_SenderInfo
            if not self.query:
                session.add_all([SenderInfo(id=sender_id)])
                session.commit()
                self.query = session.query(SenderInfo).filter_by(id=sender_id).first()

        @property
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def query_SenderInfo(self):
            return session.query(SenderInfo).filter_by(id=self.sender_id).first()

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
            self.query = session.query(CommandTriggerTime).filter_by(targetId=str(msg.target.sender_id),
                                                                     commandName=name).first()
            self.need_insert = True if not self.query else False

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
            session.add_all([CommandTriggerTime(targetId=self.msg.target.sender_id, commandName=self.name)])
            session.commit()
            session.expire_all()

    class GroupBlockList:
        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def check(target_id):
            session.expire_all()
            query = session.query(GroupBlockList).filter_by(targetId=target_id).first()
            if query:
                return True
            return False

        def add(target_id):
            session.add(GroupBlockList(targetId=target_id))
            session.commit()
            return True

        def remove(target_id):
            entry = session.query(GroupBlockList).filter_by(targetId=target_id).first()
            if entry:
                session.delete(entry)
                session.commit()
                return True
            else:
                return False


    class Data:
        def __init__(self, msg: Union[MessageSession, FetchTarget, str]):
            if isinstance(msg, MessageSession):
                self.targetName = msg.target.client_name
            elif isinstance(msg, FetchTarget):
                self.targetName = msg.name
            else:
                self.targetName = msg

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
            if not exists:
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
            session.add(AnalyticsData(targetId=self.target.target.target_id,
                                      senderId=self.target.target.sender_id,
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
            if module_name:
                filter_.append(AnalyticsData.moduleName == module_name)
            return session.query(AnalyticsData).filter(*filter_).all()

        @staticmethod
        def get_count_by_times(new, old, module_name=None):
            filter_ = [AnalyticsData.timestamp < new, AnalyticsData.timestamp > old]
            if module_name:
                filter_.append(AnalyticsData.moduleName == module_name)
            return session.query(AnalyticsData).filter(*filter_).count()

    class UnfriendlyActions:
        def __init__(self, target_id, sender_id):
            self.target_id = target_id
            self.sender_id = sender_id

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def check_mute(self) -> bool:
            """

            :return: True = yes, False = no
            """
            query = session.query(UnfriendlyActionsTable).filter_by(targetId=self.target_id).all()
            unfriendly_list = []
            for records in query:
                if datetime.datetime.now().timestamp() - records.timestamp.timestamp() < 432000:
                    unfriendly_list.append(records)
            if len(unfriendly_list) > 5:
                return True
            count = {}
            for criminal in unfriendly_list:
                if datetime.datetime.now().timestamp() - criminal.timestamp.timestamp() < 86400:
                    if criminal.sender_id not in count:
                        count[criminal.sender_id] = 0
                    else:
                        count[criminal.sender_id] += 1
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
            session.add_all([UnfriendlyActionsTable(targetId=self.target_id,
                                                    senderId=self.sender_id, action=action, detail=detail)])
            session.commit()
            return self.check_mute()

    class JobQueue:

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(target_client: str, action: str, args: dict):
            taskid = str(uuid.uuid4())
            session.add_all([JobQueueTable(taskid=taskid, targetClient=target_client, action=action,
                                           args=json.dumps(args))])
            session.commit()
            session.expire_all()
            return taskid

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        def get(taskid: str) -> JobQueueTable:
            return session.query(JobQueueTable).filter_by(taskid=taskid).first()

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        def get_first(target_client: str) -> JobQueueTable:
            return session.query(JobQueueTable).filter_by(targetClient=target_client, hasDone=False).first()

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        def get_all(target_client: str) -> List[JobQueueTable]:
            return session.query(JobQueueTable).filter_by(targetClient=target_client, hasDone=False).all()

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def return_val(query: JobQueueTable, value):
            query.returnVal = json.dumps(value)
            query.hasDone = True
            session.commit()
            session.expire_all()
            return True

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def clear(time=43200):
            queries = session.query(JobQueueTable).all()
            for q in queries:
                if datetime.datetime.now().timestamp() - q.timestamp.timestamp() > time:
                    session.delete(q)
            session.commit()
            session.expire_all()
            return True


__all__ = ["BotDBUtil", "auto_rollback_error", "session"]
