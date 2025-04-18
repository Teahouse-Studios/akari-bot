import asyncio
from typing import Union

import orjson as json
from fastapi import WebSocket

from core.builtins import (
    Plain,
    I18NContext,
    confirm_command,
    FinishedSession
)
from bots.web.info import *
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.temp import Temp
from core.config import Config
from core.constants.exceptions import WaitCancelException
from core.logger import Logger
from core.types import Session, MsgInfo



class MessageSession(MessageSessionT):
    websocket: WebSocket
    session: Union[Session]

    class Feature:
        image = True
        voice = False
        mention = False
        embed = False
        forward = False
        delete = False
        markdown = True
        quote = False
        rss = False
        typing = False
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
        websocket = Temp.data.get("web_chat_websocket")
        if websocket:
            message_chain = MessageChain(message_chain)
            self.sent.append(message_chain)
            send_msg_chain = []
            for x in message_chain.as_sendable(self, embed=False):
                if isinstance(x, PlainElement):
                    send_msg_chain.append({"type": "text", "content": x.text})
                    Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
                elif isinstance(x, ImageElement):
                    img_b64 = await x.get_base64(mime=True)
                    send_msg_chain.append({"type": "image", "content": img_b64})
                    Logger.info(f"[Bot] -> [{self.target.target_id}]: Image: {img_b64[:100]}...")
            
            await websocket.send_text(json.dumps(send_msg_chain).decode())

        return FinishedSession(self, [0], ["Should be a callable here... hmm..."])


    async def wait_confirm(
        self,
        message_chain=None,
        quote=True,
        delete=True,
        timeout=120,
        append_instruction=True,
    ):
        if Config("no_confirm", False):
            return True
        websocket = Temp.data.get("web_chat_websocket")
        if websocket:
            if message_chain:
                message_chain = MessageChain(message_chain)
                if append_instruction:
                    message_chain.append(I18NContext("message.wait.prompt.confirm"))
                await self.send_message(message_chain)
            try:
                c = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            except asyncio.TimeoutError:
                raise WaitCancelException
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
        websocket = Temp.data.get("web_chat_websocket")
        if websocket:
            if message_chain:
                message_chain = MessageChain(message_chain)
                if append_instruction:
                    message_chain.append(I18NContext("message.wait.prompt.next_message"))
                await self.send_message(message_chain)
            try:
                c = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            except asyncio.TimeoutError:
                raise WaitCancelException
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
        websocket = Temp.data.get("web_chat_websocket")
        if websocket:
            message_chain = MessageChain(message_chain)
            if append_instruction:
                message_chain.append(I18NContext("message.reply.prompt"))
            try:
                c = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            except asyncio.TimeoutError:
                raise WaitCancelException
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
                )
            )

    async def wait_anyone(
        self, message_chain=None, quote=True, delete=False, timeout=120
    ):
        websocket = Temp.data.get("web_chat_websocket")
        if websocket:
            if message_chain:
                message_chain = MessageChain(message_chain)
                await self.send_message(message_chain)
            try:
                c = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
            except asyncio.TimeoutError:
                raise WaitCancelException
            self.session.message = c
            return self

    def as_display(self, text_only=False):
        return self.session.message

    async def to_message_chain(self):
        return MessageChain(Plain(self.session.message))

    async def delete(self):
        return True

    async def check_permission(self):
        return True

    async def check_native_permission(self):
        return True

    def check_super_user(self):
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
