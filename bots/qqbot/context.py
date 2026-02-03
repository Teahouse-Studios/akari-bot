import asyncio
import html

from botpy.api import BotAPI
from botpy.errors import ServerError
from botpy.http import Route
from botpy.message import BaseMessage, C2CMessage, DirectMessage, GroupMessage, Message
from botpy.types.message import Media, Reference

from bots.qqbot.features import Features
from bots.qqbot.info import client_name, target_group_prefix, target_guild_prefix
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, MentionElement
from core.builtins.message.internal import Image, I18NContext
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.config import Config
from core.logger import Logger
from core.utils.http import url_pattern
from core.utils.image import msgchain2image, msgnode2image

qq_typing_emoji = str(Config("qq_typing_emoji", 181, (str, int), table_name="bot_qqbot"))
qq_limited_emoji = str(Config("qq_limited_emoji", 10060, (str, int), table_name="bot_qqbot"))
enable_send_url = Config("qq_bot_enable_send_url", False, table_name="bot_qqbot")


# 额外添加平台接口支持但 SDK 不支持的方法
# https://github.com/tencent-connect/botpy/pull/215
class ModdedBotAPI(BotAPI):
    async def recall_group_message(
            self,
            group_openid: str,
            message_id: str) -> str:
        route = Route(
            "DELETE",
            "/v2/groups/{group_openid}/messages/{message_id}",
            group_openid=group_openid,
            message_id=message_id,
        )
        return await self._http.request(route)

    async def post_group_file(
        self,
        group_openid: str,
        file_type: int,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> Media:
        payload = locals()
        payload.pop("self", None)
        route = Route("POST", "/v2/groups/{group_openid}/files", group_openid=group_openid)
        return await self._http.request(route, json=payload)

    async def post_c2c_file(
        self,
        openid: str,
        file_type: int,
        url: str | None = None,
        srv_send_msg: bool = False,
        file_data: str | None = None,
    ) -> Media:
        payload = locals()
        payload.pop("self", None)
        route = Route("POST", "/v2/users/{openid}/files", openid=openid)
        return await self._http.request(route, json=payload)


class QQBotContextManager(ContextManager):
    context: dict[str, BaseMessage] = {}
    features: Features | None = Features

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: BaseMessage):
        from bots.qqbot.bot import client  # noqa

        context._api = ModdedBotAPI(http=client.http)
        cls.context[session_info.session_id] = context

    @classmethod
    async def check_native_permission(cls, session_info: SessionInfo) -> bool:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        # 这里可以添加权限检查的逻辑
        ctx: BaseMessage = cls.context.get(session_info.session_id)

        if ctx:
            if isinstance(ctx, Message):
                info = ctx.member
                admins = ["2", "4"]
                for x in admins:
                    if x in info.roles:
                        return True
            elif isinstance(ctx, DirectMessage):
                return True
            elif isinstance(ctx, GroupMessage):
                ...  # 群组好像无法获取成员权限信息...
            elif isinstance(ctx, C2CMessage):
                return True
        return False

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain | MessageNodes, quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: BaseMessage = cls.context.get(session_info.session_id)
        msg_ids = []

        if isinstance(message, MessageNodes):
            message = MessageChain.assign(await msgnode2image(message))

        plains: list[PlainElement] = []
        images: list[ImageElement] = []

        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            if isinstance(x, PlainElement):
                x.text = html.unescape(x.text)
                if enable_parse_message:
                    x.text = match_atcode(x.text, client_name, "<@{uid}>")
                plains.append(x)
            elif isinstance(x, ImageElement):
                images.append(x)
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_guild_prefix:
                    plains.append(PlainElement(text=f"<@{x.id}>"))
        if len(plains + images) != 0:
            msg = "\n".join([x.text for x in plains]).strip()

            filtered_msg = []
            lines = msg.split("\n")
            for line in lines:
                if enable_send_url:
                    def process_url(match):
                        url_ = match.group(0)
                        parts = url_.split(".")
                        for i in range(1, len(parts)):
                            if parts[i] and parts[i][0].isalpha():
                                parts[i] = parts[i][0].upper() + parts[i][1:]
                        return ".".join(parts)

                    line = url_pattern.sub(process_url, line)
                elif url_pattern.findall(line):
                    continue
                filtered_msg.append(line)
            msg = "\n".join(filtered_msg).strip()
            image_1 = None
            send_img = None

            if ctx:
                if isinstance(ctx, Message):
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                    send_img = await image_1.get() if image_1 else None
                    msg_quote = (
                        Reference(
                            message_id=ctx.id,
                            ignore_get_message_error=False,
                        )
                        if quote and not send_img
                        else None
                    )
                    if not msg_quote and quote:
                        msg = f"<@{ctx.author.id}> \n" + msg
                    msg = "" if not msg else msg
                    send = await ctx.reply(
                        content=msg, file_image=send_img, message_reference=msg_quote
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(
                            f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}"
                        )
                    if send:
                        msg_ids.append(send["id"])
                    if images:
                        for img in images:
                            send_img = await img.get()
                            send = await ctx.reply(file_image=send_img)
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}"
                            )
                            if send:
                                msg_ids.append(send["id"])
                elif isinstance(ctx, DirectMessage):
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                    send_img = await image_1.get() if image_1 else None
                    msg_quote = (
                        Reference(
                            message_id=ctx.id,
                            ignore_get_message_error=False,
                        )
                        if quote and not send_img
                        else None
                    )
                    msg = "" if not msg else msg
                    send = await ctx.reply(
                        content=msg, file_image=send_img, message_reference=msg_quote
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(
                            f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}"
                        )
                    if send:
                        msg_ids.append(send["id"])
                    if images:
                        for img in images:
                            send_img = await img.get()
                            send = await ctx.reply(file_image=send_img)
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}"
                            )
                            if send:
                                msg_ids.append(send["id"])
                elif isinstance(ctx, GroupMessage):
                    seq = (
                        ctx.msg_seq if ctx.msg_seq else 1
                    )
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await ctx._api.post_group_file(
                            group_openid=ctx.group_openid,
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    if msg and ctx.id:
                        msg = "\n" + msg
                    msg = "" if not msg else msg
                    try:
                        send = await ctx.reply(
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}"
                            )
                        if send:
                            msg_ids.append(send["id"])
                            seq += 1
                    except ServerError:
                        img_chain = filtered_msg
                        img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                        if image_1:
                            img_chain.append(image_1)
                        imgs = await msgchain2image(img_chain, session_info)
                        if imgs:
                            imgs = [Image(img) for img in imgs]
                            images = imgs + images
                    if images:
                        for img in images:
                            send_img = await ctx._api.post_group_file(
                                group_openid=ctx.group_openid,
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await ctx.reply(
                                msg_type=7, media=send_img, msg_seq=seq
                            )
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}"
                            )
                            if send:
                                msg_ids.append(send["id"])
                                seq += 1
                    ctx.msg_seq = seq
                elif isinstance(ctx, C2CMessage):
                    seq = (
                        ctx.msg_seq if ctx.msg_seq else 1
                    )
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await ctx._api.post_c2c_file(
                            openid=ctx.author.user_openid,
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    msg = "" if not msg else msg
                    try:
                        send = await ctx.reply(
                            content=msg,
                            msg_type=7 if send_img else 0,
                            media=send_img,
                            msg_seq=seq,
                        )
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                        if image_1:
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}"
                            )
                        if send:
                            msg_ids.append(send["id"])
                            seq += 1
                    except ServerError:
                        img_chain = filtered_msg
                        img_chain.insert(0, I18NContext("error.message.limited.msg2img"))
                        if image_1:
                            img_chain.append(image_1)
                        imgs = await msgchain2image(img_chain, session_info)
                        if imgs:
                            imgs = [Image(img) for img in imgs]
                            images = imgs + images
                    if images:
                        for img in images:
                            send_img = await ctx._api.post_c2c_file(
                                openid=ctx.author.user_openid,
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await ctx.reply(
                                msg_type=7, media=send_img, msg_seq=seq
                            )
                            Logger.info(
                                f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}"
                            )
                            if send:
                                msg_ids.append(send["id"])
                                seq += 1
                    ctx.msg_seq = seq

        return msg_ids

    @classmethod
    async def delete_message(cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        from bots.qqbot.bot import client  # noqa

        client.api = ModdedBotAPI(http=client.http)
        if session_info.target_from == target_guild_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_message(
                        channel_id=session_info.get_common_target_id(),
                        message_id=msg_id,
                        hidetip=True
                    )
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")
        elif session_info.target_from == target_group_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_group_message(
                        group_openid=session_info.get_common_target_id(),
                        message_id=msg_id
                    )
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")

    @classmethod
    async def add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2

            from bots.qqbot.bot import client  # noqa
            try:
                await client.api.put_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
                Logger.info(f"Added reaction \"{emoji}\" to message {message_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to add reaction \"{emoji}\" to message {
                                 message_id} in session {session_info.session_id}: ")

    @classmethod
    async def remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2

            from bots.qqbot.bot import client  # noqa
            try:
                await client.api.delete_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
                Logger.info(f"Removed reaction \"{emoji}\" to message {
                            message_id} in session {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to remove reaction \"{emoji}\" to message {
                                 message_id} in session {session_info.session_id}: ")

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            Logger.debug(f"Start typing in session: {session_info.session_id}")

            if session_info.target_from == target_guild_prefix:
                emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2

                from bots.qqbot.bot import client  # noqa

                await client.api.put_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=session_info.message_id,
                    emoji_type=emoji_type,
                    emoji_id=qq_typing_emoji,
                )

            flag = asyncio.Event()
            cls.typing_flags[session_info.session_id] = flag
            await flag.wait()

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            del cls.typing_flags[session_info.session_id]
        # 这里可以添加结束输入状态的逻辑
        Logger.debug(f"End typing in session: {session_info.session_id}")

    @classmethod
    async def error_signal(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        # 这里可以添加错误处理逻辑

        if session_info.target_from == target_guild_prefix:
            emoji_type = 1 if int(qq_limited_emoji) < 9000 else 2

            from bots.qqbot.bot import client  # noqa

            await client.api.put_reaction(
                channel_id=session_info.get_common_target_id(),
                message_id=session_info.message_id,
                emoji_type=emoji_type,
                emoji_id=qq_limited_emoji,
            )
