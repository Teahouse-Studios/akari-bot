import qqbot

from core.bots.qqchannel.token import token
from core.elements import MessageSession as MS, FinishedSession as FinS, Plain
from core.elements.message.chain import MessageChain

msg_api = qqbot.AsyncMessageAPI(token, False)
member_api = qqbot.AsyncGuildMemberAPI(token, False)


class FinishedSession(FinS):
    def __init__(self, result: list):
        self.result = result

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...


class MessageSession(MS):

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
        msgchain = MessageChain(msgchain)
        plains = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                plains.append(x)
        print(plains)
        if len(plains) != 0:
            msg = '\n'.join([x.text for x in plains])
            request = qqbot.MessageSendRequest(msg, msg_id=self.session.message.id)
            print(self.session.target.split('|')[1])
            send = await msg_api.post_message(self.session.target.split('|')[1], request)
            return FinishedSession([send.id])

    async def waitConfirm(self, msgchain=None, quote=True):
        """
        一次性模板，用于等待触发对象确认。
        :param msgchain: 需要发送的确认消息，可不填
        :param quote: 是否引用传入dict中的消息（默认为True）
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
        """
        ...

    def asDisplay(self):
        """
        用于将消息转换为一般文本格式。
        """
        return self.session.message.content

    async def delete(self):
        """
        用于删除这条消息。
        """
        ...

    async def checkPermission(self):
        """
        用于检查消息发送者在对象内的权限。
        """
        if self.target.senderInfo.check_TargetAdmin(self.target.targetId) \
            or self.target.senderInfo.query.isSuperUser:
            return True
        return self.checkNativePermission()

    async def checkNativePermission(self):
        """
        用于检查消息发送者原本在聊天平台中是否具有管理员权限。
        """
        info = await member_api.get_guild_member(self.session.target.split('|')[0], self.session.sender)
        admins = ["2", "4"]
        for x in admins:
            if x in info.roles:
                return True
        return False

    def checkSuperUser(self):
        """
        用于检查消息发送者是否为超级用户。
        """
        return True if self.target.senderInfo.query.isSuperUser else False

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class Feature:
        """
        此消息来自的客户端所支持的消息特性一览，用于不同平台适用特性判断（如QQ支持消息类型的语音而Discord不支持）
        """
        image = False
        voice = False
        embed = False
        forward = False
        delete = False
        quote = False
        wait = False
