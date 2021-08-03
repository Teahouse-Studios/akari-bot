import re
from .message import MessageSession
from core.elements import MsgInfo, Session
from .broadcast import app


class Bot:
    all_func = ("fetch_target",)

    @staticmethod
    def fetch_target(targetId):
        matchTarget = re.match(r'^(QQ|(?:Group\||))(.*)', targetId)
        if matchTarget:
            if matchTarget.group(1) == 'QQ|Group':
                target = app.getGroup(int(matchTarget.group(2)))
            else:
                target = app.getFriend(int(matchTarget.group(2)))
            if target is not None:
                return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                              targetFrom=matchTarget.group(1), senderFrom=matchTarget.group(1)),
                                      Session(message=False, target=target, sender=target))
