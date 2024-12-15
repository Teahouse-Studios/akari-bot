import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Union, List

import orjson as json
from sqlalchemy import func
from tenacity import retry, stop_after_attempt

from core.builtins import MessageSession, FetchTarget, FetchedSession
from core.constants import database_version
from core.database.orm import Session
from core.database.tables import *
from core.exports import add_export
from core.utils.text import isint

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
    database_version = database_version
    time_offset = None

    class TargetInfo:
        def __init__(self, msg: Union[MessageSession, FetchTarget, str]):
            if isinstance(msg, (MessageSession, FetchTarget)):
                self.target_id = str(msg.target.target_id)
            else:
                self.target_id = msg
            self.query = self.query_data

        @property
        def query_data(self):
            return (
                session.query(TargetInfoTable)
                .filter_by(targetId=self.target_id)
                .first()
            )

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def init(self):
            if not self.query:
                session.add_all([TargetInfoTable(targetId=self.target_id)])
                session.commit()
                return self.query_data
            return self.query

        @property
        def enabled_modules(self) -> list:
            if not self.query:
                return []
            return json.loads(self.query.enabledModules)

        def check_target_enabled_module(self, module_name) -> bool:
            return module_name in self.enabled_modules

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

        def get_option(self, k=None, default=None):
            if not self.query:
                if not k:
                    return {}
                return default

            if not k:
                return self.options
            return self.options.get(k, default)

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
            return json.loads(self.query.customAdmins)

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
            self.query.customAdmins = json.dumps(custom_admins)
            session.commit()
            return True

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove_custom_admin(self, sender_id) -> bool:
            if self.query:
                custom_admins = self.custom_admins.copy()
                if sender_id in custom_admins:
                    custom_admins.remove(sender_id)
                self.query.customAdmins = json.dumps(custom_admins)
            return True

        @property
        def locale(self):
            if not self.query:
                self.query = self.init()
            return self.query.locale

        @staticmethod
        def get_target_list(module_name=None, id_prefix=None) -> List[TargetInfoTable]:
            filter_ = []
            if module_name:
                filter_.append(
                    TargetInfoTable.enabledModules.like(f'%"{module_name}"%')
                )
            if id_prefix:
                filter_.append(TargetInfoTable.targetId.like(f"{id_prefix}%"))
            return session.query(TargetInfoTable).filter(*filter_).all()

    class SenderInfo:
        def __init__(self, sender_id):
            self.sender_id = sender_id
            self.query = self.query_SenderInfo

        @property
        def query_SenderInfo(self):
            return session.query(SenderInfo).filter_by(id=self.sender_id).first()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def init(self):
            if not self.query:
                session.add_all([SenderInfo(id=self.sender_id)])
                session.commit()
                return self.query_SenderInfo
            return self.query

        @property
        def is_in_block_list(self):
            if not self.query:
                return False
            return self.query.isInBlockList

        @property
        def is_in_allow_list(self):
            if not self.query:
                return False
            return self.query.isInAllowList

        @property
        def is_super_user(self):
            if not self.query:
                return False
            return self.query.isSuperUser

        @property
        def warns(self):
            if not self.query:
                return 0
            return self.query.warns

        @property
        def disable_typing(self):
            if not self.query:
                return False
            return self.query.disableTyping

        @property
        def petal(self):
            if not self.query:
                return 0
            if self.query.petal < 0:
                self.query.petal = 0
            return self.query.petal

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def modify_petal(self, amount: int) -> bool:
            if not self.query:
                self.query = self.init()
            petal = self.petal
            if not isint(amount):
                amount = Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            new_petal = petal + int(amount)
            new_petal = 0 if new_petal < 0 else new_petal
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

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def edit(self, column: str, value):
            if not self.query:
                self.query = self.init()
            setattr(self.query, column, value)
            session.commit()
            session.expire_all()
            return True

        @staticmethod
        def get_sender_list(id_prefix=None) -> List[SenderInfo]:
            filter_ = []
            if id_prefix:
                filter_.append(SenderInfo.id.like(f"{id_prefix}%"))
            return session.query(SenderInfo).filter(*filter_).all()

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

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(target_id):
            session.add(GroupBlockList(targetId=target_id))
            session.commit()
            return True

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def remove(target_id):
            entry = session.query(GroupBlockList).filter_by(targetId=target_id).first()
            if entry:
                session.delete(entry)
                session.commit()
                return True
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
            session.add(StoredData(name=f"{self.targetName}|{name}", value=value))
            session.commit()

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def get(self, name):
            return (
                session.query(StoredData)
                .filter_by(name=f"{self.targetName}|{name}")
                .first()
            )

        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def update(self, name, value: Union[str, bytes]):
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
            session.add(
                AnalyticsData(
                    targetId=self.target.target.target_id,
                    senderId=self.target.target.sender_id,
                    command="*".join(command[::2]),
                    moduleName=module_name,
                    moduleType=module_type,
                )
            )
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

        @staticmethod
        def get_modules_count():
            results = (
                session.query(AnalyticsData.moduleName, func.count(AnalyticsData.id))
                .group_by(AnalyticsData.moduleName)
                .all()
            )
            modules_count = dict(results)
            return modules_count

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
            query = (
                session.query(UnfriendlyActionsTable)
                .filter_by(targetId=self.target_id)
                .all()
            )
            unfriendly_list = []
            for records in query:
                if (
                    datetime.datetime.now().timestamp() - records.timestamp.timestamp()
                    < 432000
                ):
                    unfriendly_list.append(records)
            if len(unfriendly_list) > 5:
                return True
            count = {}
            for criminal in unfriendly_list:
                if (
                    datetime.datetime.now().timestamp() - criminal.timestamp.timestamp()
                    < 86400
                ):
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
        def add(self, action="default", detail=""):
            """

            :return: True = yes, False = no
            """
            session.add_all(
                [
                    UnfriendlyActionsTable(
                        targetId=self.target_id,
                        senderId=self.sender_id,
                        action=action,
                        detail=detail,
                    )
                ]
            )
            session.commit()

    class JobQueue:

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        @auto_rollback_error
        def add(target_client: str, action: str, args: dict):
            taskid = str(uuid.uuid4())
            session.add_all(
                [
                    JobQueueTable(
                        taskid=taskid,
                        targetClient=target_client,
                        action=action,
                        args=json.dumps(args),
                    )
                ]
            )
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
            return (
                session.query(JobQueueTable)
                .filter_by(targetClient=target_client, hasDone=False)
                .first()
            )

        @staticmethod
        @retry(stop=stop_after_attempt(3))
        def get_all(target_client: str) -> List[JobQueueTable]:
            return (
                session.query(JobQueueTable)
                .filter_by(targetClient=target_client, hasDone=False)
                .all()
            )

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


add_export(BotDBUtil)
__all__ = ["BotDBUtil", "auto_rollback_error", "session"]
