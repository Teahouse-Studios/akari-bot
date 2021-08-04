import re
from .message import Template
from core.elements import MsgInfo, Session
from .client import client


class Bot:
    all_func = ("fetch_target",)

    @staticmethod
    def fetch_target(targetId):
        matchChannel = re.match(r'^(DC|(?:DM\||)Channel)|(.*)', targetId)
        if matchChannel:
            getChannel = client.get_channel(int(matchChannel.group(2)))
            return Template(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom=matchChannel.group(1), senderFrom=matchChannel.group(1)),
                                  Session(message=False, target=getChannel, sender=getChannel))
        else:
            return False
