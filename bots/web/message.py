import asyncio
import uuid
from typing import Union

import orjson as json
from fastapi import WebSocket

from core.builtins import (
    Bot,
    Plain,
    MessageTaskManager,
    FinishedSession as FinS,
    FetchTarget as FetchTargetT
)
from bots.web.info import *
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.temp import Temp
from core.logger import Logger
from core.types import Session


class FinishedSession(FinS):
    async def delete(self):
        pass


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
        websocket: WebSocket = Temp.data["web_chat_websocket"]
        message_chain = MessageChain(message_chain)
        self.sent.append(message_chain)
        sends = []
        for x in message_chain.as_sendable(self, embed=False):
            if isinstance(x, PlainElement):
                sends.append({"type": "text", "content": x.text, "id": str(uuid.uuid4())})
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                img_b64 = await x.get_base64(mime=True)
                sends.append({"type": "image", "content": img_b64, "id": str(uuid.uuid4())})
                Logger.info(f"[Bot] -> [{self.target.target_id}]: Image: {img_b64[:50]}...")
        
        await websocket.send_text(json.dumps(sends).decode())

        msg_ids = []
        for x in sends:
            msg_ids.append(x["id"])
            if callback:
                MessageTaskManager.add_callback(x["id"], callback)
        return FinishedSession(self, msg_ids, sends)

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
    asDisplay = as_display
    toMessageChain = to_message_chain
    checkPermission = check_permission
    checkNativePermission = check_native_permission
    checkSuperUser = check_super_user


class FetchTarget(FetchTargetT):
    name = client_name

    @staticmethod
    async def fetch_target(target_id, sender_id=None):
        if target_id == f"{target_prefix}|0":
            return FetchedSession(
                target_from=target_prefix,
                target_id="0",
                sender_from=sender_prefix,
                sender_id="0",
            )

    @staticmethod
    async def post_message(module_name, message, user_list=None, i18n=False, **kwargs):
        fetch = await FetchTarget.fetch_target(f"{target_prefix}|0")
        if i18n:
            await fetch.send_direct_message(I18NContext(message, **kwargs))
        else:
            await fetch.send_direct_message(message)


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
