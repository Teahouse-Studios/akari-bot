class MessageTaskManager:
    _list = {}
    _guild_list = {}

    @staticmethod
    def add_task(uid, tsk):
        MessageTaskManager._list.update({uid: tsk})

    @staticmethod
    def del_task(uid):
        del MessageTaskManager._list[uid]

    @staticmethod
    def get():
        return MessageTaskManager._list

    @staticmethod
    def add_guild_task(uid, tsk):
        MessageTaskManager._guild_list.update({uid: tsk})

    @staticmethod
    def del_guild_task(uid):
        del MessageTaskManager._guild_list[uid]

    @staticmethod
    def guild_get():
        return MessageTaskManager._guild_list


class FinishedTasks:
    _list = {}
    _guild_list = {}

    @staticmethod
    def add_task(uid, result):
        FinishedTasks._list.update({uid: result})

    @staticmethod
    def del_task(uid):
        del FinishedTasks._list[uid]

    @staticmethod
    def get():
        return FinishedTasks._list

    @staticmethod
    def add_guild_task(uid, result):
        FinishedTasks._guild_list.update({uid: result})

    @staticmethod
    def del_guild_task(uid):
        del FinishedTasks._guild_list[uid]

    @staticmethod
    def guild_get():
        return FinishedTasks._guild_list
