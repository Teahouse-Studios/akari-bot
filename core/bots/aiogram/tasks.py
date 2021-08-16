class MessageTaskManager:
    _list = {}

    @staticmethod
    def add_task(uid, tsk):
        MessageTaskManager._list.update({uid: tsk})

    @staticmethod
    def del_task(uid):
        del MessageTaskManager._list[uid]

    @staticmethod
    def get():
        return MessageTaskManager._list


class FinishedTasks:
    _list = {}

    @staticmethod
    def add_task(uid, result: bool):
        FinishedTasks._list.update({uid: result})

    @staticmethod
    def del_task(uid):
        del FinishedTasks._list[uid]

    @staticmethod
    def get():
        return FinishedTasks._list
