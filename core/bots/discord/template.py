import re
from .message import MessageSession
from core.elements import MsgInfo, Session
from .client import client


class Bot:
    @staticmethod
    def bind_template(template):
        for x in template.all_func:
            setattr(Bot, x, getattr(template, x))

    @staticmethod
    def fetch_target(targetId):
        matchChannel = re.match(r'^(DC|(?:DM\||)Channel)|(.*)', targetId)
        if matchChannel:
            getChannel = client.get_channel(int(matchChannel.group(2)))
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=getChannel, sender=getChannel))
