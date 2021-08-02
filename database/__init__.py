import datetime

from database.orm import session
from database.tables import EnabledModules, SenderInfo, TargetAdmin, CommandTriggerTime
from core.elements import MsgInfo, MessageSession


def convert_list_to_str(lst: list) -> str:
    return '|'.join(lst)


def convert_str_to_list(s: str) -> list:
    return s.split('|')


class BotDBUtil:
    class Module:
        def __init__(self, msg: MessageSession):
            self.message = msg
            self.query = session.query(EnabledModules).filter_by(targetId=str(msg.target.targetId)).first()
            self.enable_modules_list = convert_str_to_list(self.query.enabledModules) if self.query is not None else []
            self.need_insert = True if self.query is None else False

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
                table = EnabledModules(targetId=str(self.message.target.targetId),
                                       enabledModules=value)
                session.add_all([table])
            else:
                self.query.enabledModules = value
            session.commit()
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
                self.query.enabledModules = convert_list_to_str(self.enable_modules_list)
                session.commit()
            return True

    class SenderInfo:
        def __init__(self, senderId):
            self.senderId = senderId
            self.query = session.query(SenderInfo).filter_by(id=senderId).first()
            if self.query is None:
                session.add_all([SenderInfo(id=senderId)])
                session.commit()
                self.query = session.query(SenderInfo).filter_by(id=senderId).first()

        def edit(self, column: str, value):
            setattr(self.query, column, value)
            session.commit()

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
            self.query = session.query(CommandTriggerTime).filter_by(targetId=str(msg.target.targetId), commandName=name).first()
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
