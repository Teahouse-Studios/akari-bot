class MsgInfo:
    __slots__ = ["targetId", "senderId", "senderName", "targetFrom", "senderInfo", "senderFrom"]

    def __init__(self,
                 targetId: [int, str],
                 senderId: [int, str],
                 senderName: str,
                 targetFrom: str,
                 senderFrom: str
                 ):
        self.targetId = targetId
        self.senderId = senderId
        self.senderName = senderName
        self.targetFrom = targetFrom
        self.senderFrom = senderFrom


class Session:
    def __init__(self, message, target, sender):
        self.message = message
        self.target = target
        self.sender = sender


class MessageSession:
    __slots__ = ("target", "session", "trigger_msg", "parsed_msg",
                 "sendMessage", "waitConfirm", "checkPermission", "delete", 'asDisplay', "Typing")

    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session

    @staticmethod
    def bind_template(template):
        for x in template.all_func:
            setattr(MessageSession, x, getattr(template, x))



