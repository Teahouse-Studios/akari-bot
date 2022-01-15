from typing import List

from PIL import Image

from core.elements import MessageSession, Plain, Image as BImage, Session, MsgInfo, FetchTarget as FT, Voice, Embed, FetchedSession as FS
from core.elements.others import confirm_command
from core.elements.message.chain import MessageChain
from core.logger import Logger


class Template(MessageSession):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False) -> MessageSession:
        Logger.info(msgchain)
        msgchain = MessageChain(msgchain)
        Logger.info(msgchain)
        msg_list = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                msg_list.append(x.text)
                print(x.text)
            if isinstance(x, BImage):
                img = Image.open(await x.get())
                img.show()
        return MessageSession(target=self.target,
                              session=Session(message=str(msg_list), target='TEST|Console', sender='TEST|Console'))

    async def waitConfirm(self, msgchain=None, quote=True):
        if msgchain is not None:
            await self.sendMessage(msgchain)
            print("（发送“是”或符合确认条件的词语来确认）")
        c = input('Confirm: ')
        print(c)
        if c in confirm_command:
            return True
        return False

    def asDisplay(self):
        return self.session.message

    async def delete(self):
        print("(Try to delete {self.session.message}, but I'm a console so I cannot do it :< )")
        return True

    async def checkPermission(self):
        print("(Try to check your permissions, but this is a unit test environment. Have fun!)")
        return True

    async def checkNativePermission(self):
        print("(Try to check your native permissions, but this is a unit test environment. Have fun!)")
        return True

    def checkSuperUser(self):
        print("(Try to check if you are superuser, but this is a unit test environment. Have fun!)")
        return True

    class Typing:
        def __init__(self, msg: MessageSession):
            self.msg = msg

        async def __aenter__(self):
            print('Console is typing...')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FS):
    def __init__(self, targetFrom, targetId):
        self.target = MsgInfo(targetId=f'{targetFrom}|{targetId}',
                              senderId=f'{targetFrom}|{targetId}',
                              targetFrom=targetFrom,
                              senderFrom=targetFrom,
                              senderName='')
        self.session = Session(message=False, target=targetId, sender=targetId)
        self.parent = Template(self.target, self.session)

    async def sendMessage(self, msgchain, disable_secret_check=False):
        """
        用于向获取对象发送消息。
        :param msgchain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        return await self.parent.sendMessage(msgchain, disable_secret_check=disable_secret_check, quote=False)


class FetchTarget(FT):
    name = 'TEST'

    @staticmethod
    async def fetch_target(targetId) -> FetchedSession:
        return FetchedSession('TEST|Console', targetId)

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None):
        fetch = await FetchTarget.fetch_target('0')
        await fetch.sendMessage(message)
