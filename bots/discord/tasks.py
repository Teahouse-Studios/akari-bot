class MessageTaskManager:
    _list = {}

    @staticmethod
    def add_task(grp, uid, tsk):
        MessageTaskManager._list.update({grp: {uid: tsk}})

    @staticmethod
    def del_task(grp, uid):
        del MessageTaskManager._list[grp][uid]

    @staticmethod
    def get():
        return MessageTaskManager._list


class FinishedTasks:
    _list = {}

    @staticmethod
    def add_task(grp, uid, result):
        FinishedTasks._list.update({grp: {uid: result}})

    @staticmethod
    def del_task(grp, uid):
        del FinishedTasks._list[grp][uid]

    @staticmethod
    def get():
        return FinishedTasks._list
