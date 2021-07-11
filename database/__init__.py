from database.orm import session
from database.tables import EnabledModules
from core.elements import Target


class BotDBUtil:
    class Module:
        def __init__(self, kwargs):
            self.kwargs = kwargs
            self.query = session.query(EnabledModules).filter_by(TargetId=kwargs[Target].fromId).first()
            self.enable_modules_list = self.query.EnabledModules.split('|') if self.query is not None else []
            self.need_insert = True if self.query is None else False

        def check_target_enabled_module(self, module_name) -> bool:
            return True if module_name in self.enable_modules_list else False

        def enable(self, module_name) -> bool:
            self.enable_modules_list.append(module_name)
            enabled_list = '|'.join(self.enable_modules_list)
            if self.need_insert:
                table = EnabledModules(TargetId=self.kwargs[Target].fromId, EnabledModules=enabled_list)
                session.add_all([table])
            else:
                self.query.EnabledModules = enabled_list
            session.commit()
            return True

        def disable(self, module_name) -> bool:
            del self.enable_modules_list[module_name]
            enabled_list = '|'.join(self.enable_modules_list)
            if not self.need_insert:
                self.query.EnabledModules = enabled_list
                session.commit()
            return True