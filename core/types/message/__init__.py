import asyncio
from typing import List, Union, Dict

from core.exceptions import FinishedException
from .chain import MessageChain


class MsgInfo:
    __slots__ = ["targetId", "senderId", "senderName", "targetFrom", "senderInfo", "senderFrom", "clientName",
                 "messageId", "replyId"]

    def __init__(self,
                 targetId: Union[int, str],
                 senderId: Union[int, str],
                 senderName: str,
                 targetFrom: str,
                 senderFrom: str,
                 clientName: str,
                 messageId: Union[int, str],
                 replyId: Union[int, str] = None):
        self.targetId = targetId
        self.senderId = senderId
        self.senderName = senderName
        self.targetFrom = targetFrom
        self.senderFrom = senderFrom
        self.clientName = clientName
        self.messageId = messageId
        self.replyId = replyId

    def __repr__(self):
        return f'MsgInfo(targetId={self.targetId}, senderId={self.senderId}, senderName={self.senderName},' \
               f' targetFrom={self.targetFrom}, senderFrom={self.senderFrom}, clientName={self.clientName}, ' \
               f'messageId={self.messageId}, replyId={self.replyId})'


class Session:
    def __init__(self, message, target, sender):
        self.message = message
        self.target = target
        self.sender = sender

    def __repr__(self):
        return f'Session(message={self.message}, target={self.target}, sender={self.sender})'


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
    def __init__(self, session, messageId: Union[List[int], List[str], int, str], result):
        self.session = session
        if isinstance(messageId, (int, str)):
            messageId = [messageId]
        self.messageId = messageId
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    def __str__(self):
        return f"FinishedSession(messageId={self.messageId}, result={self.result})"


class MessageSession:
    """
    消息会话，囊括了处理一条消息所需要的东西。
    """
    __slots__ = (
        "target", "session", "trigger_msg", "parsed_msg", "matched_msg", "sent", "prefixes", "options",
        "enabled_modules", "muted", "custom_admins", "data", "locale", "timestamp")

    parsed_msg: Dict[str, str]

    def __init__(self,
                 target: MsgInfo,
                 session: Session):
        self.target = target
        self.session = session
        self.sent: List[MessageChain] = []
        self.prefixes: List[str] = []
        self.options: dict = {}
        self.enabled_modules: List[str] = []
        self.muted: bool = False
        self.timestamp: float = 0

    async def sendMessage(self,
                          msgchain,
                          quote=True,
                          disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        """
        用于向消息发送者回复消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :return: 被发送的消息链
        """
        raise NotImplementedError

    async def finish(self,
                     msgchain=None,
                     quote=True,
                     disable_secret_check=False,
                     allow_split_image=True):
        """
        用于向消息发送者回复消息并终结会话（模块后续代码不再执行）。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :return: 被发送的消息链
        """
        ...
        f = None
        if msgchain is not None:
            f = await self.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=quote,
                                       allow_split_image=allow_split_image)
        raise FinishedException(f)

    async def sendDirectMessage(self, msgchain, disable_secret_check=False, allow_split_image=True):
        """
        用于向消息发送者直接发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :return: 被发送的消息链
        """
        await self.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=False,
                               allow_split_image=allow_split_image)

    async def waitConfirm(self, msgchain=None, quote=True, delete=True):
        """
        一次性模板，用于等待触发对象确认。
        :param msgchain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
        """
        raise NotImplementedError

    async def waitNextMessage(self, msgchain=None, quote=True, delete=False, append_instruction=True):
        """
        一次性模板，用于等待对象的下一条消息。
        :param msgchain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息
        :return: 下一条消息的MessageChain对象
        """
        raise NotImplementedError

    async def waitReply(self, msgchain, quote=True, all_=False, append_instruction=True):
        """
        一次性模板，用于等待触发对象回复消息。
        :param msgchain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param all_: 是否设置触发对象为对象内的所有人（默认为False）
        :return: 回复消息的MessageChain对象
        """
        raise NotImplementedError

    async def waitAnyone(self, msgchain=None, delete=False):
        """
        一次性模板，用于等待触发发送者所属对象内所有成员确认。
        :param msgchain: 需要发送的确认消息，可不填
        :param delete: 是否在触发后删除消息
        :return: 任意人的MessageChain对象
        """
        raise NotImplementedError

    def asDisplay(self, text_only=False) -> str:
        """
        用于将消息转换为一般文本格式。
        :param text_only: 是否只保留纯文本（默认为False）
        """
        raise NotImplementedError

    async def toMessageChain(self) -> MessageChain:
        """
        用于将session.message中的消息文本转换为MessageChain。
        """
        raise NotImplementedError

    async def delete(self):
        """
        用于删除这条消息。
        """
        raise NotImplementedError

    async def checkPermission(self):
        """
        用于检查消息发送者在对象内的权限。
        """
        raise NotImplementedError

    async def checkNativePermission(self):
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        raise NotImplementedError

    async def fake_forward_msg(self, nodelist):
        """
        用于发送假转发消息（QQ）。
        """
        raise NotImplementedError

    async def get_text_channel_list(self):
        """
        用于获取子文字频道列表（QQ）。
        """
        raise NotImplementedError

    class Typing:
        def __init__(self, msg):
            """
            :param msg: 本条消息，由于此class需要被一同传入下游方便调用，所以作为子class存在，将来可能会有其他的解决办法。
            """

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def checkSuperUser(self):
        """
        用于检查消息发送者是否为超级用户。
        """
        raise NotImplementedError

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def call_api(self, action, **params):
        raise NotImplementedError

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
        return "Message(target={}, session={}, sent={})".format(self.target, self.session, self.sent)


class FetchedSession:
    def __init__(self, targetFrom, targetId, senderFrom=None, senderId=None):
        if senderFrom is None:
            senderFrom = targetFrom
        if senderId is None:
            senderId = targetId
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{senderId}',
                              targetFrom=targetFrom,
                              senderFrom=senderFrom,
                              senderName='', clientName='', replyId=None, messageId=0)
        self.session = Session(message=False, target=targetId, sender=senderId)
        self.parent = MessageSession(self.target, self.session)

    async def sendDirectMessage(self, msgchain, disable_secret_check=False, allow_split_image=True):
        """
        用于向获取对象发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :return: 被发送的消息链
        """
        return await self.parent.sendDirectMessage(msgchain, disable_secret_check, allow_split_image=allow_split_image)


class FetchTarget:
    name = ''

    @staticmethod
    async def fetch_target(targetId) -> FetchedSession:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        raise NotImplementedError

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[FetchedSession]:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        raise NotImplementedError

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None, i18n=False, **kwargs):
        """
        尝试向开启此模块的对象发送一条消息。
        :param module_name: 模块名
        :param message: 消息文本
        :param user_list: 用户列表
        :param i18n: 是否使用i18n，若为True则message为i18n的key（或为指定语言的dict映射表（k=语言，v=文本））
        """
        raise NotImplementedError


__all__ = ["FetchTarget", "MsgInfo", "MessageSession", "Session", "FetchedSession", "FinishedSession", "AutoSession"]
