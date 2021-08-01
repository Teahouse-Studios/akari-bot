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
    __slots__ = ("target", "session", "trigger_msg", "parsed_msg",)

    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session

    async def sendMessage(self, msgchain, quote=True): ...

    async def waitConfirm(self): ...

    def asDisplay(self): ...

    async def delete(self): ...

    def checkPermission(self): ...

    class Typing:
        def __init__(self, msg): ...

    def checkSuperUser(self): ...

    class Feature:
        image = ...
        voice = ...
