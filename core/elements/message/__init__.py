class Target:
    def __init__(self,
        fromId,
        fromName,
        senderId,
        senderName,
        msgFrom
    ):
        self.fromId = fromId
        self.fromName = fromName
        self.senderId = senderId
        self.senderName = senderName
        self.msgFrom = msgFrom


class InfoChain:
    def __init__(self,
                 target,
                 messageChain):
        self.target = target
        self.messageChain = messageChain


class Plain:
    def __init__(self,
                 text):
        self.text = text


class Image:
    def __init__(self,
                 url=None,
                 path=None):
        ...