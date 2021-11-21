from typing import List

from PIL import Image

from core.elements import MessageSession, Plain, Image as BImage, Session, MsgInfo, FetchTarget as FT
from core.elements.others import confirm_command
from core.secret_check import Secret


class Template(MessageSession):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = True

    async def sendMessage(self, msgchain, quote=True) -> MessageSession:
        if Secret.find(msgchain):
            return await self.sendMessage('https://wdf.ink/6Oup')
        if isinstance(msgchain, str):
            print(msgchain)
            return MessageSession(target=self.target,
                                  session=Session(message=msgchain, target='TEST|Console', sender='TEST|Console'))
        if isinstance(msgchain, list):
            msg_list = []
            for x in msgchain:
                if isinstance(x, Plain):
                    print(x.text)
                    msg_list.append(x.text)
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


class FetchTarget(FT):
    @staticmethod
    async def fetch_target(targetId):
        return Template(target=MsgInfo(targetId=targetId,
                                       senderId=targetId,
                                       senderName='',
                                       targetFrom='TEST|Console',
                                       senderFrom='TEST|Console'),
                        session=Session(message=False, target=targetId, sender=targetId))

    @staticmethod
    async def post_message(module_name, message, user_list: List[MessageSession] = None):
        if isinstance(message, str):
            print(message)
        elif isinstance(message, list):
            for x in message:
                if isinstance(x, Plain):
                    print(x.text)
                if isinstance(x, BImage):
                    img = Image.open(await x.get())
                    img.show()
        return message
