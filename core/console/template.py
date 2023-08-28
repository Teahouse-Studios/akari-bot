from typing import List, Union

from PIL import Image

from core.builtins import Plain, Image as BImage, confirm_command, Bot, FetchTarget as FT, FetchedSession as FS
from core.builtins.message import MessageSession as MS
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import Session, MsgInfo, FinishedSession as FinS, AutoSession as AS, AutoSession


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        print("(Tried to delete message, but I'm a console so I cannot do it :< )")


class Template(MS):
    session: Union[Session, AS]

    class Feature:
        image = True
        voice = False
        forward = False
        delete = True
        wait = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        msgchain = MessageChain(msgchain)
        self.sent.append(msgchain)
        msg_list = []
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                msg_list.append(x.text)
                print(x.text)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            if isinstance(x, BImage):
                image_path = await x.get()
                img = Image.open(image_path)
                img.show()
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {image_path}')
        return FinishedSession(self, [0], ['There should be a callable here... hmm...'])

    async def waitConfirm(self, msgchain=None, quote=True, delete=True):
        send = None
        if msgchain is not None:
            send = await self.sendMessage(msgchain)
            print("（发送“是”或符合确认条件的词语来确认）")
        print(self.session.auto_interactions)
        if self.session.auto_interactions:
            c = self.session.auto_interactions[0]
            del self.session.auto_interactions[0]
        else:
            c = input('Confirm: ')
        print(c)
        if msgchain is not None and delete:
            await send.delete()
        if c in confirm_command:
            return True

        return False

    async def waitAnyone(self, msgchain=None, quote=True, delete=True):
        send = None
        if msgchain is not None:
            send = await self.sendMessage(msgchain)
        if self.session.auto_interactions:
            c = self.session.auto_interactions[0]
            del self.session.auto_interactions[0]
        else:
            c = input('Confirm: ')
        print(c)
        if msgchain is not None and delete:
            await send.delete()
        self.session.message = c
        return self

    async def waitReply(self, msgchain, quote=True, all_=False, append_instruction=True):
        msgchain = MessageChain(msgchain)
        if append_instruction:
            msgchain.append(Plain(self.locale.t("message.reply.prompt")))
        send = await self.sendMessage(msgchain, quote)
        c = input('Reply: ')
        return Template(target=MsgInfo(targetId='TEST|Console|0',
                                       senderId='TEST|0',
                                       senderName='',
                                       targetFrom='TEST|Console',
                                       senderFrom='TEST', clientName='TEST', messageId=0,
                                       replyId=None),
                        session=AutoSession(message=c, target='TEST|Console|0', sender='TEST|0',
                                            auto_interactions=None))

    def asDisplay(self, text_only=False):
        return self.session.message

    async def toMessageChain(self):
        return MessageChain(Plain(self.session.message))

    async def delete(self):
        print(
            f"(Tried to delete {self.session.message}, but I'm a console so I cannot do it :< )")
        return True

    async def checkPermission(self):
        print("(Tried to check your permissions, but this is a console. Have fun!)")
        return True

    async def checkNativePermission(self):
        print("(Tried to check your native permissions, but this is a console. Have fun!)")
        return True

    def checkSuperUser(self):
        print("(Try to check if you are superuser, but this is a unit test environment. Have fun!)")
        return True

    async def sleep(self, s):
        print("(Tried to sleep for %d seconds, skip.)" % s)

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            print('Console is typing...')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FS):

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
    async def fetch_target(targetId, senderId=None) -> FetchedSession:
        return FetchedSession('TEST|Console', '0', 'TEST', '0')

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None, i18n=False, **kwargs):
        fetch = await FetchTarget.fetch_target('0')
        if i18n:
            await fetch.sendMessage(fetch.parent.locale.t(message, **kwargs))
        else:
            await fetch.sendMessage(message)


Bot.MessageSession = Template
Bot.FetchTarget = FetchTarget
