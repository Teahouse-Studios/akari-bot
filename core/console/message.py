from typing import List, Union

from PIL import Image
import aioconsole

from core.builtins import (Plain, Image as BImage, confirm_command, Bot, FetchTarget as FetchTargetT,
                           FetchedSession as FetchedSessionT)
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import Session, MsgInfo, FinishedSession as FinS


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        print("(Tried to delete message, but I'm a console so I cannot do it :< )")


class MessageSession(MessageSessionT):
    session: Union[Session]

    class Feature:
        image = True
        voice = False
        forward = False
        delete = True
        wait = True

    async def send_message(self, message_chain, quote=True, disable_secret_check=False,
                           allow_split_image=True) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        self.sent.append(message_chain)
        msg_list = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, Plain):
                msg_list.append(x.text)
                print(x.text)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
            if isinstance(x, BImage):
                image_path = await x.get()
                img = Image.open(image_path)
                img.show()
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {image_path}')
        return FinishedSession(self, [0], ['There should be a callable here... hmm...'])

    async def wait_confirm(self, message_chain=None, quote=True, delete=True):
        send = None
        if message_chain is not None:
            send = await self.send_message(message_chain)
            print(self.locale.t("message.wait.confirm.prompt.type1"))

        c = await aioconsole.ainput('Confirm: ')
        print(c)
        if message_chain is not None and delete:
            await send.delete()
        if c in confirm_command:
            return True

        return False

    async def wait_anyone(self, message_chain=None, quote=True, delete=True):
        send = None
        if message_chain is not None:
            send = await self.send_message(message_chain)
        c = await aioconsole.ainput('Confirm: ')
        print(c)
        if message_chain is not None and delete:
            await send.delete()
        self.session.message = c
        return self

    async def wait_reply(self, message_chain, quote=True, all_=False, append_instruction=True):
        message_chain = MessageChain(message_chain)
        if append_instruction:
            message_chain.append(Plain(self.locale.t("message.reply.prompt")))
        send = await self.send_message(message_chain, quote)
        c = await aioconsole.ainput('Reply: ')
        return MessageSession(target=MsgInfo(target_id='TEST|Console|0',
                                             sender_id='TEST|0',
                                             sender_name='',
                                             target_from='TEST|Console',
                                             sender_from='TEST', client_name='TEST', message_id=0,
                                             reply_id=None),
                              session=Session(message=c, target='TEST|Console|0', sender='TEST|0'))

    def as_display(self, text_only=False):
        return self.session.message

    async def to_message_chain(self):
        return MessageChain(Plain(self.session.message))

    async def delete(self):
        print(
            f"(Tried to delete {self.session.message}, but I'm a console so I cannot do it :< )")
        return True

    async def check_permission(self):
        print("(Tried to check your permissions, but this is a console. Have fun!)")
        return True

    async def check_native_permission(self):
        print("(Tried to check your native permissions, but this is a console. Have fun!)")
        return True

    def check_super_user(self):
        print("(Try to check if you are superuser, but this is a unit test environment. Have fun!)")
        return True

    async def sleep(self, s):
        print("(Tried to sleep for %d seconds, skip.)" % s)

    sendMessage = send_message
    waitConfirm = wait_confirm
    waitReply = wait_reply
    waitAnyone = wait_anyone
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkPermission = check_permission
    checkNativePermission = check_native_permission
    checkSuperUser = check_super_user

    class Typing:
        def __init__(self, msg: MessageSessionT):
            self.msg = msg

        async def __aenter__(self):
            print('Console is typing...')

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FetchedSessionT):

    async def send_message(self, message_chain, disable_secret_check=False):
        """
        用于向获取对象发送消息。
        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        return await self.parent.send_message(message_chain, disable_secret_check=disable_secret_check, quote=False)


class FetchTarget(FetchTargetT):
    name = 'TEST'

    @staticmethod
    async def fetch_target(target_id, sender_id=None) -> FetchedSession:
        return FetchedSession('TEST|Console', '0', 'TEST', '0')

    @staticmethod
    async def post_message(module_name, message, user_list: List[FetchedSession] = None, i18n=False, **kwargs):
        fetch = await FetchTarget.fetch_target('0')
        if i18n:
            await fetch.send_message(fetch.parent.locale.t(message, **kwargs))
        else:
            await fetch.send_message(message)


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
