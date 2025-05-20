import asyncio
import re
import traceback
import uuid
from typing import Union

import orjson as json
from fastapi import WebSocket

from core.builtins import (
    Bot,
    Plain,
    Image,
    I18NContext,
    MessageTaskManager,
    FinishedSession as FinS,
    FetchTarget as FetchTargetT
)
from core.builtins.message import MessageSession as MessageSessionT
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement
from core.builtins.temp import Temp
from core.logger import Logger
from core.types import Session
from .info import *


class FinishedSession(FinS):
    async def delete(self):
        try:
            websocket: WebSocket = Temp.data["web_chat_websocket"]

            resp = {"action": "delete", "id": self.message_id}
            await websocket.send_text(json.dumps(resp).decode())
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MessageSessionT):
    websocket: WebSocket
    session: Union[Session]

    class Feature:
        image = True
        voice = False
        mention = False
        embed = False
        forward = False
        delete = True
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
                sends.append({"type": "text", "content": x.text})
                Logger.info(f"[Bot] -> [{self.target.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                img_b64 = await x.get_base64(mime=True)
                sends.append({"type": "image", "content": img_b64})
                Logger.info(f"[Bot] -> [{self.target.target_id}]: Image: {img_b64[:50]}...")

        resp = {"action": "send", "message": sends, "id": str(uuid.uuid4())}
        await websocket.send_text(json.dumps(resp).decode())

        if callback:
            MessageTaskManager.add_callback(resp["id"], callback)
        return FinishedSession(self, resp["id"], sends)

    def as_display(self, text_only=False):
        msgs = []
        for msg in self.session.message["message"]:
            if msg["type"] == "text":
                msgs.append(msg["content"])
        return "\n".join(msgs)

    async def to_message_chain(self):
        msg_chain = MessageChain()
        for msg in self.session.message["message"]:
            if msg["type"] == "text":
                msg_chain.append(Plain(msg["content"]))
            elif msg["type"] == "image":
                msg_chain.append(Image(msg["content"]))
        return msg_chain

    async def delete(self):
        try:
            websocket: WebSocket = Temp.data["web_chat_websocket"]
            resp = {"action": "delete", "id": [self.session.message["id"]]}
            await websocket.send_text(json.dumps(resp).decode())
            return True
        except Exception:
            Logger.error(traceback.format_exc())
            return False

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
        target_pattern = r"|".join(re.escape(item) for item in target_prefix_list)
        match_target = re.match(rf"^({target_pattern})\|(.*)", target_id)
        if match_target:
            target_from = match_target.group(1)
            target_id = match_target.group(2)
            sender_from = None
            if sender_id:
                sender_pattern = r"|".join(
                    re.escape(item) for item in sender_prefix_list
                )
                match_sender = re.match(rf"^({sender_pattern})\|(.*)", sender_id)
                if match_sender:
                    sender_from = match_sender.group(1)
                    sender_id = match_sender.group(2)
            session = Bot.FetchedSession(target_from, target_id, sender_from, sender_id)
            await session.parent.data_init()
            return session

    @staticmethod
    async def post_message(module_name, message, user_list=None, i18n=False, **kwargs):
        fetch = await FetchTarget.fetch_target(f"{target_prefix}|0")
        if i18n:
            await fetch.send_direct_message(I18NContext(message, **kwargs))
        else:
            await fetch.send_direct_message(message)


Bot.MessageSession = MessageSession
Bot.FetchTarget = FetchTarget
