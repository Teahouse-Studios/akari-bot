from core.elements import MessageSession


class MessageTaskManager:
    _list = {}

    @staticmethod
    def add_task(session: MessageSession, flag, all_=False):
        sender = session.target.senderId
        if all_:
            sender = 'all'

        MessageTaskManager._list.update(
            {session.target.targetId: {sender: {'flag': flag, 'active': True}}})

    @staticmethod
    def get_result(session: MessageSession):
        return MessageTaskManager._list[session.target.targetId][session.target.senderId]['result']

    @staticmethod
    def get():
        return MessageTaskManager._list

    @staticmethod
    def check(session: MessageSession):
        if session.target.targetId in MessageTaskManager._list:
            sender = None
            if session.target.senderId in MessageTaskManager._list[session.target.targetId]:
                sender = session.target.senderId
            if 'all' in MessageTaskManager._list[session.target.targetId]:
                sender = 'all'
            if sender is not None:
                MessageTaskManager._list[session.target.targetId][sender]['result'] = session
                MessageTaskManager._list[session.target.targetId][sender]['active'] = False
                MessageTaskManager._list[session.target.targetId][sender]['flag'].set()


__all__ = ['MessageTaskManager']
