import asyncio
from typing import Union

from PIL import Image as PILImage
from inputimeout import inputimeout, TimeoutOccurred

from core.builtins import (
    Plain,
    I18NContext,
    confirm_command,
    Bot,
    FetchTarget as FetchTargetT,
    FetchedSession as FetchedSessionT,
    FinishedSession as FinS,
)
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.config import Config
from core.console.info import *
from core.constants.exceptions import WaitCancelException
from core.logger import Logger
from core.types import Session, MsgInfo


class FinishedSession(FinS):
    async def delete(self):
        print("(Tried to delete message, but I\'m a console so I cannot do it :< )")


class MessageSession(MessageSessionT):
    session: Union[Session]

    class Feature:
        image = True
        voice = False
        mention = False
        embed = False
        forward = False
        delete = False
        markdown = False
        quote = False
        rss = True
        typing = True
        wait = True

    async def send_message(
        self,
        message_chain,
        quote=True,
        disable_secret_check=False,
        enable_parse_message=True,
        enable_split_image=True,
        callback=None,
    ) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        self.sent.append(message_chain)
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, PlainElement):
                print(x.text)
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                image_path = await x.get()
                img = PILImage.open(image_path)
                img.show()
                Logger.info(f"[Bot] -> [{self.target.target_id}]: Image: {image_path}")
        return FinishedSession(self, [0], ["Should be a callable here... hmm..."])

    async def wait_confirm(
        self,
        message_chain=None,
        quote=True,
        delete=True,
        timeout=120,
        append_instruction=True,
    ):
        send = None
        if Config("no_confirm", False):
            return True
        if message_chain:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.prompt.confirm"))
            send = await self.send_message(message_chain)
        try:
            if timeout:
                c = inputimeout("Confirm: ", timeout=timeout)
            else:
                c = input("Confirm: ")
        except TimeoutOccurred:
            if message_chain and delete:
                await send.delete()
            raise WaitCancelException
        if message_chain and delete:
            await send.delete()
        if c in confirm_command:
            return True
        return False

    async def wait_next_message(
        self,
        message_chain=None,
        quote=True,
        delete=False,
        timeout=120,
        append_instruction=True,
    ):
        send = None
        if message_chain:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.wait.prompt.next_message"))
            send = await self.send_message(message_chain)
        try:
            if timeout:
                c = inputimeout("Confirm: ", timeout=timeout)
            else:
                c = input("Confirm: ")
        except TimeoutOccurred:
            if message_chain and delete:
                await send.delete()
            raise WaitCancelException
        if message_chain and delete:
            await send.delete()
        self.session.message = c
        return self

    async def wait_reply(
        self,
        message_chain,
        quote=True,
        delete=False,
        timeout=120,
        all_=False,
        append_instruction=True,
    ):
        message_chain = MessageChain(message_chain)
        if append_instruction:
            message_chain.append(I18NContext("message.reply.prompt"))
        send = await self.send_message(message_chain)
        try:
            if timeout:
                c = inputimeout("Reply: ", timeout=timeout)
            else:
                c = input("Reply: ")
        except TimeoutOccurred:
            if message_chain and delete:
                await send.delete()
            raise WaitCancelException
        if message_chain and delete:
            await send.delete()
        return MessageSession(
            target=MsgInfo(
                target_id=f"{target_prefix}|0",
                sender_id=f"{sender_prefix}|0",
                sender_name="Console",
                target_from=target_prefix,
                sender_from=sender_prefix,
                client_name=client_name,
                message_id=0,
            ),
            session=Session(
                message=c, target=f"{target_prefix}|0", sender=f"{sender_prefix}|0"
            ),
        )

    async def wait_anyone(
        self, message_chain=None, quote=True, delete=False, timeout=120
    ):
        send = None
        if message_chain:
            message_chain = MessageChain(message_chain)
            send = await self.send_message(message_chain)
        try:
            if timeout:
                c = inputimeout("Confirm: ", timeout=timeout)
            else:
                c = input("Confirm: ")
        except TimeoutOccurred:
            if message_chain and delete:
                await send.delete()
            raise WaitCancelException
        if message_chain and delete:
            await send.delete()
        self.session.message = c
        return self

    def as_display(self, text_only=False):
        return self.session.message

    async def to_message_chain(self):
        return MessageChain(Plain(self.session.message))

    async def delete(self):
        print(
            f"(Tried to delete {self.session.message}, but I\'m a console so I cannot do it :< )"
        )
        return True

    async def check_permission(self):
        print("(Tried to check your permissions, but this is a console. Have fun!)")
        return True

    async def check_native_permission(self):
        print(
            "(Tried to check your native permissions, but this is a console. Have fun!)"
        )
        return True

    def check_super_user(self):
        print(
            "(Try to check if you are superuser, but this is a unit test environment. Have fun!)"
        )
        return True

    async def sleep(self, s):
        await asyncio.sleep(s)

    sendMessage = send_message
    waitConfirm = wait_confirm
    waitNextMessage = wait_next_message
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
            print("Console is typing...")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


class FetchedSession(FetchedSessionT):

    async def send_direct_message(self, message_chain, disable_secret_check=False):
        """
        用于向获取对象发送消息。

        :param message_chain: 消息链，若传入str则自动创建一条带有Plain元素的消息链
        :param disable_secret_check: 是否禁用消息检查（默认为False）
        :return: 被发送的消息链
        """
        await self.parent.data_init()
        return await self.parent.send_message(
            message_chain, disable_secret_check=disable_secret_check, quote=False
        )


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None):
        if target_id == "TEST|Console|0":
            return FetchedSession(
                target_from=target_prefix,
                target_id="0",
                sender_from=sender_prefix,
                sender_id="0",
            )

    @staticmethod
    async def post_message(module_name, message, user_list=None, i18n=False, **kwargs):
        fetch = await FetchTarget.fetch_target("TEST|Console|0")
        if i18n:
            await fetch.send_direct_message(I18NContext(message, **kwargs))
        else:
            await fetch.send_direct_message(message)


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
