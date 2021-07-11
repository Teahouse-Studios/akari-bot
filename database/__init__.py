from database.orm import session
from database.tables import EnabledModules
from core.elements.elements import Target


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