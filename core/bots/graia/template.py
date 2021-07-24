import traceback

from graia.application import MessageChain, GroupMessage, FriendMessage
from graia.application.friend import Friend
from graia.application.group import Group, Member
from graia.application.message.elements.internal import Plain, Image
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter

from core.elements import Plain as BPlain, Image as BImage, MessageSession
from core.bots.graia.broadcast import app, bcc


class Template:
    all_func = ("sendMessage", "waitConfirm", "asDisplay", "revokeMessage", "checkPermission", "Typing")

    async def sendMessage(self, msg: MessageSession, msgchain, quote=True):
        """
        用于发送一条消息，兼容Group和Friend消息。
        :param msg: 函数传入的dict
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param quote: 是否引用传入dict中的消息（仅对Group消息有效）
        :return: 被发送的消息链
        """
        if isinstance(msgchain, str):
            if msgchain == '':
                msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
            msgchain = MessageChain.create([Plain(msgchain)])
        if isinstance(msgchain, list):
            msgchain_list = []
            for x in msgchain:
                if isinstance(x, BPlain):
                    msgchain_list.append(Plain(x.text))
                if isinstance(x, BImage):
                    msgchain_list.append(Image.fromLocalFile(x.image))
            if not msgchain_list:
                msgchain_list.append(Plain('发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'))
            msgchain = MessageChain.create(msgchain_list)
        if isinstance(msg.session.target, Group):
            send = await app.sendGroupMessage(msg.session.target, msgchain)
            return send
        if isinstance(msg.session.target, Friend):
            send = await app.sendFriendMessage(msg.session.target, msgchain)
            return send

    async def waitConfirm(self, msg: MessageSession):
        """
        一次性模板，用于等待触发对象确认，兼容Group和Friend消息
        :param msg: 函数传入的dict
        :return: 若对象发送confirm_command中的其一文本时返回True，反之则返回False
        """
        inc = InterruptControl(bcc)
        confirm_command = ["是", "对", '确定', '是吧', '大概是',
                           '也许', '可能', '对的', '是呢', '对呢', '嗯', '嗯呢',
                           '吼啊', '资瓷', '是呗', '也许吧', '对呗', '应该',
                           'yes', 'y', 'yeah', 'yep', 'ok', 'okay', '⭐', '√']
        if isinstance(msg.session.target, Group):
            @Waiter.create_using_function([GroupMessage])
            def waiter(waiter_group: Group,
                       waiter_member: Member, waiter_message: MessageChain):
                if all([
                    waiter_group.id == msg.session.target.id,
                    waiter_member.id == msg.session.sender.id,
                ]):
                    if waiter_message.asDisplay() in confirm_command:
                        return True
                    else:
                        return False
        if isinstance(msg.session.target, Friend):
            @Waiter.create_using_function([FriendMessage])
            def waiter(waiter_friend: Friend, waiter_message: MessageChain):
                if all([
                    waiter_friend.id == msg.session.sender.id,
                ]):
                    if waiter_message.asDisplay() in confirm_command:
                        return True
                    else:
                        return False

        return await inc.wait(waiter)

    def asDisplay(self, msg: MessageSession):
        display = msg.session.message.asDisplay()
        return display

    async def revokeMessage(self, send_msg):
        """
        用于撤回消息。
        :param send_msg: 需要撤回的已发送/接收的消息链
        :return: 无返回
        """
        try:
            if isinstance(send_msg, list):
                for msg in send_msg:
                    await app.revokeMessage(msg)
            else:
                await app.revokeMessage(send_msg)
        except:
            traceback.print_exc()

    def checkPermission(self, msg: MessageSession):
        """
        检查对象是否拥有某项权限
        :param msg: 从函数传入的dict
        :return: 若对象为群主、管理员或机器人超管则为True
        """
        if isinstance(msg.session.target, Group):
            if str(msg.session.sender.permission) in ['MemberPerm.Administrator', 'MemberPerm.Owner'] \
                    or msg.target.senderInfo.query.isSuperUser \
                    or msg.target.senderInfo.check_TargetAdmin(msg.target.targetId):
                return True
        if isinstance(msg.session.target, Friend):
            return True
        return False

    class Typing:
        def __init__(self, msg: MessageSession):
            self.msg = msg

        async def __aenter__(self):
            if isinstance(self.msg.session.target, Group):
                await app.nudge(self.msg.session.sender)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


