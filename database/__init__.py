from database.orm import session
from database.tables import EnabledModules, BlackList, WhiteList, WarnList, SuperUser, FromAdmin
from core.elements import Target


def convert_list_to_str(lst: list) -> str:
    return '|'.join(lst)


def convert_str_to_list(s: str) -> list:
    return s.split('|')


class BotDBUtil:
    class Module:
        def __init__(self, infochain):
            self.infochain = infochain
            self.query = session.query(EnabledModules).filter_by(TargetId=infochain[Target].fromId).first()
            self.enable_modules_list = convert_str_to_list(self.query.EnabledModules) if self.query is not None else []
            self.need_insert = True if self.query is None else False

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enable_modules_list else False

        def enable(self, module_name) -> bool:
            if module_name not in self.enable_modules_list:
                self.enable_modules_list.append(module_name)
            value = convert_list_to_str(self.enable_modules_list)
            if self.need_insert:
                table = EnabledModules(TargetId=self.infochain[Target].fromId,
                                       EnabledModules=value)
                session.add_all([table])
            else:
                self.query.EnabledModules = value
            session.commit()
            return True

        def disable(self, module_name) -> bool:
            if module_name in self.enable_modules_list:
                self.enable_modules_list.remove(module_name)
            if not self.need_insert:
                self.query.EnabledModules = convert_list_to_str(self.enable_modules_list)
                session.commit()
            return True

    class TargetInfo:
        def __init__(self, infochain):
            self.infochain = infochain
            self.isInBlackList = True if session.query(BlackList).filter_by(TargetId=infochain[Target].fromId).first() is not None else False
            self.isInWhiteList = True if session.query(WhiteList).filter_by(TargetId=infochain[Target].fromId).first() is not None else False
            self.isBanned = True if self.isInBlackList and not self.isInWhiteList else False
            self.isSuperUser = True if session.query(SuperUser).filter_by(TargetId=infochain[Target].fromId).first() is not None else False
            check_warn = session.query(SuperUser).filter_by(TargetId=infochain[Target].fromId).first()
            self.Warns = 0 if check_warn is None else check_warn.Frequency


    class SetSenderTarget:
        def __init__(self, infochain):
            self.sender = infochain[Target].senderId
            self.from_ = infochain[Target].fromId

        def to_something(self, table):
            query = session.query(table).filter_by(TargetId=self.sender).first()
            if query is None:
                session.add_all([table])
                session.commit()
            return True

        def remove_from_something(self, table):
            query = session.query(table).filter_by(TargetId=self.sender).first()
            if query is not None:
                query.delete()
                session.commit()
            return True

        def to_blacklist(self):
            return True if self.to_something(BlackList(TargetId=self.sender)) else False

        def to_whitelist(self):
            return True if self.to_something(WhiteList(TargetId=self.sender)) else False

        def to_superuser(self):
            return True if self.to_something(SuperUser(TargetId=self.sender)) else False

        def to_warnlist(self, freq):
            return True if self.to_something(WarnList(TargetId=self.sender, Frequency=freq)) else False

        def to_fromadmin(self):
            return True if self.to_something(FromAdmin(TargetId=self.sender, FromId=self.from_)) else False

        def remove_from_blacklist(self):
            return True if self.remove_from_something(BlackList) else False

        def remove_from_whitelist(self):
            return True if self.remove_from_something(WhiteList) else False

        def remove_from_superuser(self):
            return True if self.remove_from_something(SuperUser) else False

        def remove_from_warnlist(self):
            return True if self.remove_from_something(WarnList) else False

        def remove_from_fromadmin(self):
            query = session.query(FromAdmin).filter_by(TargetId=self.sender, FromId=self.from_).first()
            if query is not None:
                query.delete()
                session.commit()
            return True



