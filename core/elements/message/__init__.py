import asyncio
from typing import List

from core.elements.message.chain import MessageChain
from core.exceptions import FinishedException


class MsgInfo:
    __slots__ = ["targetId", "senderId", "senderName", "targetFrom", "senderInfo", "senderFrom", "clientName"]

    def __init__(self,
                 targetId: [int, str],
                 senderId: [int, str],
                 senderName: str,
                 targetFrom: str,
                 senderFrom: str,
                 clientName: str
                 ):
        self.targetId = targetId
        self.senderId = senderId
        self.senderName = senderName
        self.targetFrom = targetFrom
        self.senderFrom = senderFrom
        self.clientName = clientName


class Session:
    def __init__(self, message, target, sender):
        self.message = message
        self.target = target
        self.sender = sender


class AutoSession(Session):
    """
    For autotest
    """
    def __init__(self, message, target, sender, auto_interactions=None):
        super().__init__(message, target, sender)
        if auto_interactions is None:
            auto_interactions = []
        self.auto_interactions = auto_interactions


class FinishedSession:
    def __init__(self, result: list):
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    def __str__(self):
        """
        <FinishedSession: {str(self.result)}>
        """
        return f"<FinishedSession: {str(self.result)}>"


class MessageSession:
    """
    消息会话，囊括了处理一条消息所需要的东西。
    """
    __slots__ = ("target", "session", "trigger_msg", "parsed_msg", "matched_msg", "sent")

    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session
        self.sent: List[MessageChain] = []

    async def sendMessage(self,
                          msgchain,
                          quote=True,
                          disable_secret_check=False) -> FinishedSession:
        """
        用于向消息发送者回复消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        ...

    async def finish(self,
                     msgchain=None,
                     quote=True,
                     disable_secret_check=False):
        """
        用于向消息发送者回复消息并终结会话（模块后续代码不再执行）。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        ...
        f = None
        if msgchain is not None:
            f = await self.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=quote)
        raise FinishedException(f)

    async def sendDirectMessage(self, msgchain, disable_secret_check=False):
        """
        用于向消息发送者直接发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        await self.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=False)

    async def waitConfirm(self, msgchain=None, quote=True, delete=True):
        """
        一次性模板，用于等待触发对象确认。
        :param msgchain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
        """
        ...

    async def waitAnyone(self, msgchain=None, delete=False):
        """
        一次性模板，用于等待触发发送者所属对象内所有成员确认。
        :param msgchain: 需要发送的确认消息，可不填
        :param delete: 是否在触发后删除消息
        :return: 任意人的一条文本消息。
        """
        ...

    def asDisplay(self):
        """
        用于将消息转换为一般文本格式。
        """
        ...

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    async def checkPermission(self):
        """
        用于检查消息发送者在对象内的权限。
        """
        ...

    async def checkNativePermission(self):
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        ...

    async def fake_forward_msg(self, nodelist):
        """
        用于发送假转发消息（QQ）。
        """
        ...

    async def get_text_channel_list(self):
        """
        用于获取子文字频道列表（QQ）。
        """
        ...

    class Typing:
        def __init__(self, msg):
            """
            :param msg: 本条消息，由于此class需要被一同传入下游方便调用，所以作为子class存在，将来可能会有其他的解决办法。
            """
            ...

    def checkSuperUser(self):
        """
        用于检查消息发送者是否为超级用户。
        """
        ...

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def call_api(self, action, **params):
        ...

    class Feature:
        """
        此消息来自的客户端所支持的消息特性一览，用于不同平台适用特性判断（如QQ支持消息类型的语音而Discord不支持）
        """
        image = ...
        voice = ...
        embed = ...
        forward = ...
        delete = ...
        quote = ...
        wait = ...

    def __str__(self):
        return "Message(sent={})".format(self.sent)

class FetchedSession:
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='', clientName='')
        self.session = Session(message=False, target=targetId, sender=targetId)
        self.parent = MessageSession(self.target, self.session)

    async def sendDirectMessage(self, msgchain, disable_secret_check=False):
        """
        用于向获取对象发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        return await self.parent.sendDirectMessage(msgchain, disable_secret_check)


class FetchTarget:
    name = ''

    @staticmethod
    async def fetch_target(targetId) -> FetchedSession:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        ...

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[FetchedSession]:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        ...

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None):
        """
        尝试向开启此模块的对象发送一条消息。
        """


__all__ = ["FetchTarget", "MsgInfo", "MessageSession", "Session", "FetchedSession", "FinishedSession", "AutoSession"]
