import asyncio
from typing import List, Union, Dict, Coroutine

from core.exceptions import FinishedException
from .chain import MessageChain


class MsgInfo:
    __slots__ = ["target_id", "sender_id", "sender_name", "target_from", "sender_info", "sender_from", "client_name",
                 "message_id", "reply_id"]

    def __init__(self,
                 target_id: Union[int, str],
                 sender_id: Union[int, str],
                 sender_name: str,
                 target_from: str,
                 sender_from: str,
                 client_name: str,
                 message_id: Union[int, str],
                 reply_id: Union[int, str] = None):
        self.target_id = target_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.target_from = target_from
        self.sender_from = sender_from
        self.client_name = client_name
        self.message_id = message_id
        self.reply_id = reply_id

    def __repr__(self):
        return f'MsgInfo(target_id={self.target_id}, sender_id={self.sender_id}, sender_name={self.sender_name},' \
               f' target_from={self.target_from}, sender_from={self.sender_from}, client_name={self.client_name}, ' \
               f'message_id={self.message_id}, reply_id={self.reply_id})'


class Session:
    def __init__(self, message, target, sender):
        self.message = message
        self.target = target
        self.sender = sender

    def __repr__(self):
        return f'Session(message={self.message}, target={self.target}, sender={self.sender})'


class FinishedSession:
    def __init__(self, session, message_id: Union[List[int], List[str], int, str], result):
        self.session = session
        if isinstance(message_id, (int, str)):
            message_id = [message_id]
        self.message_id = message_id
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    def __str__(self):
        return f"FinishedSession(message_id={self.message_id}, result={self.result})"


class MessageSession:
    """
    消息会话，囊括了处理一条消息所需要的东西。
    """
    __slots__ = (
        "target", "session", "trigger_msg", "parsed_msg", "matched_msg", "sent", "prefixes", "options",
        "enabled_modules", "muted", "custom_admins", "data", "locale", "timestamp", "tmp", "timezone_offset",
        "_tz_offset")

    parsed_msg: Dict[str, Union[str, list]]

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
        self.tmp = {}

    async def send_message(self,
                           message_chain,
                           quote=True,
                           disable_secret_check=False,
                           allow_split_image=True,
                           callback: Coroutine = None) -> FinishedSession:
        """
        用于向消息发送者回复消息。
        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数
        :return: 被发送的消息链
        """
        raise NotImplementedError

    async def finish(self,
                     message_chain=None,
                     quote=True,
                     disable_secret_check=False,
                     allow_split_image=True,
                     callback: Coroutine = None):
        """
        用于向消息发送者回复消息并终结会话（模块后续代码不再执行）。
        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数
        :return: 被发送的消息链
        """
        ...
        f = None
        if message_chain:
            f = await self.send_message(message_chain, disable_secret_check=disable_secret_check, quote=quote,
                                        allow_split_image=allow_split_image, callback=callback)
        raise FinishedException(f)

    async def send_direct_message(self, message_chain, disable_secret_check=False, allow_split_image=True,
                                  callback: Coroutine = None):
        """
        用于向消息发送者直接发送消息。
        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅Telegram平台使用了切割）
        :param callback: 回调函数，用于在消息发送完成后回复本消息执行的函数
        :return: 被发送的消息链
        """
        await self.send_message(message_chain, disable_secret_check=disable_secret_check, quote=False,
                                allow_split_image=allow_split_image, callback=callback)

    async def wait_confirm(self, message_chain=None, quote=True, delete=True, timeout=120, append_instruction=True):
        """
        一次性模板，用于等待触发对象确认。
        :param message_chain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息（默认为True）
        :param timeout: 超时时间
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
        """
        raise NotImplementedError

    async def wait_next_message(self, message_chain=None, quote=True, delete=False, timeout=120,
                                append_instruction=True):
        """
        一次性模板，用于等待对象的下一条消息。
        :param message_chain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息（默认为False）
        :param timeout: 超时时间
        :return: 下一条消息的MessageChain对象
        """
        raise NotImplementedError

    async def wait_reply(self, message_chain, quote=True, delete=False, timeout=120, all_=False,
                         append_instruction=True):
        """
        一次性模板，用于等待触发对象回复消息。
        :param message_chain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :param delete: 是否在触发后删除消息（默认为False）
        :param timeout: 超时时间
        :param all_: 是否设置触发对象为对象内的所有人（默认为False）
        :return: 回复消息的MessageChain对象
        """
        raise NotImplementedError

    async def wait_anyone(self, message_chain=None, quote=False, delete=False, timeout=120):
        """
        一次性模板，用于等待触发发送者所属对象内所有成员确认。
        :param message_chain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为False）
        :param delete: 是否在触发后删除消息（默认为False）
        :param timeout: 超时时间
        :return: 任意人的MessageChain对象
        """
        raise NotImplementedError

    def as_display(self, text_only=False) -> str:
        """
        用于将消息转换为一般文本格式。
        :param text_only: 是否只保留纯文本（默认为False）
        """
        raise NotImplementedError

    async def to_message_chain(self) -> MessageChain:
        """
        用于将session.message中的消息文本转换为MessageChain。
        """
        raise NotImplementedError

    async def delete(self):
        """
        用于删除这条消息。
        """
        raise NotImplementedError

    async def check_permission(self):
        """
        用于检查消息发送者在对象内的权限。
        """
        raise NotImplementedError

    async def check_native_permission(self):
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

    def ts2strftime(self, timestamp: float, date=True, iso=False, time=True, seconds=True, timezone=True):
        """
        用于将时间戳转换为可读的时间格式。
        :param timestamp: 时间戳
        :param date: 是否显示日期
        :param iso: 是否以ISO格式显示
        :param time: 是否显示时间
        :param seconds: 是否显示秒
        :param timezone: 是否显示时区
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

    def check_super_user(self):
        """
        用于检查消息发送者是否为超级用户。
        """
        raise NotImplementedError

    @staticmethod
    async def sleep(s):
        await asyncio.sleep(s)

    async def call_api(self, action, **params):
        raise NotImplementedError

    sendMessage = send_message
    sendDirectMessage = send_direct_message
    waitConfirm = wait_confirm
    waitNextMessage = wait_next_message
    waitReply = wait_reply
    waitAnyone = wait_anyone
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkPermission = check_permission
    checkNativePermission = check_native_permission
    checkSuperUser = check_super_user

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
    def __init__(self, target_from, target_id, sender_from=None, sender_id=None):
        if not sender_from:
            sender_from = target_from
        if not sender_id:
            sender_id = target_id
        self.target = MsgInfo(target_id=f'{target_from}|{target_id}',
                              sender_id=f'{target_from}|{sender_id}',
                              target_from=target_from,
                              sender_from=sender_from,
                              sender_name='', client_name='', reply_id=None, message_id=0)
        self.session = Session(message=False, target=target_id, sender=sender_id)
        self.parent = MessageSession(self.target, self.session)

    async def send_direct_message(self, message_chain, disable_secret_check=False, allow_split_image=True):
        """
        用于向获取对象发送消息。
        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :param allow_split_image: 是否允许拆分图片发送（此参数作接口兼容用，仅telegram平台使用了切割）
        :return: 被发送的消息链
        """
        return await self.parent.send_direct_message(message_chain, disable_secret_check,
                                                     allow_split_image=allow_split_image)

    sendDirectMessage = send_direct_message


class FetchTarget:
    name = ''

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> FetchedSession:
        """
        尝试从数据库记录的对象ID中取得对象消息会话，实际此会话中的消息文本会被设为False（因为本来就没有）。
        """
        raise NotImplementedError

    @staticmethod
    async def fetch_target_list(target_list: list) -> List[FetchedSession]:
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


class ModuleHookContext:
    """
    模块任务上下文。主要用于传递模块任务的参数。
    """

    def __init__(self, args: dict):
        self.args = args


__all__ = ["FetchTarget", "MsgInfo", "MessageSession", "Session", "FetchedSession", "FinishedSession",
           "ModuleHookContext", "MessageChain"]
