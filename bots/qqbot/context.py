import asyncio
import html

from botpy.api import BotAPI
from botpy.http import Route
from botpy.message import BaseMessage, C2CMessage, DirectMessage, GroupMessage, Message
from botpy.types.message import Media, Reference
# from botpy.types.message import MarkdownPayload

from bots.qqbot.features import Features
from bots.qqbot.info import (
    client_name,
    target_group_prefix,
    target_direct_prefix,
    target_guild_prefix,
    target_c2c_prefix,
)
from bots.qqbot.utils import url_filter
from core.builtins.message.chain import MessageChain, MessageNodes, match_atcode
from core.builtins.message.elements import PlainElement, ImageElement, MentionElement
from core.builtins.session.context import ContextManager
from core.builtins.session.info import SessionInfo
from core.config import Config
from core.logger import Logger

qq_typing_emoji = str(Config("qq_typing_emoji", 181, (str, int), table_name="bot_qqbot"))
qq_limited_emoji = str(Config("qq_limited_emoji", 10060, (str, int), table_name="bot_qqbot"))


# 额外添加平台接口支持但 SDK 不支持的方法
# https://github.com/tencent-connect/botpy/pull/215
class ModdedBotAPI(BotAPI):
    async def recall_group_message(self, group_openid: str, message_id: str) -> str:
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
    features: Features = Features()

    @classmethod
    def add_context(cls, session_info: SessionInfo, context: BaseMessage):
        from bots.qqbot.bot import client

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
                if ctx.author.member_role in ["admin", "owner"]:
                    return True
                else:
                    return False
            elif isinstance(ctx, C2CMessage):
                return True
        return False

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        ctx: BaseMessage = cls.context.get(session_info.session_id)
        msg_ids = []

        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")

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
            msg = url_filter(msg)
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
                    send = await ctx.reply(content=msg, file_image=send_img, message_reference=msg_quote)
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        msg_ids.append(send["id"])
                    if images:
                        for img in images:
                            send_img = await img.get()
                            send = await ctx.reply(file_image=send_img)
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
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
                    send = await ctx.reply(content=msg, file_image=send_img, message_reference=msg_quote)
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        msg_ids.append(send["id"])
                    if images:
                        for img in images:
                            send_img = await img.get()
                            send = await ctx.reply(file_image=send_img)
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                            if send:
                                msg_ids.append(send["id"])
                elif isinstance(ctx, GroupMessage):
                    seq = ctx.msg_seq if ctx.msg_seq else 1

                    msg_quote = (
                        Reference(
                            message_id=ctx.id,
                            ignore_get_message_error=False,
                        )
                        if quote and not send_img
                        else None
                    )
                    if msg and ctx.id and session_info.tmp.get("message_type") == "group_at":
                        msg = "\n" + msg
                    msg = "" if not msg else msg
                    # if msg and ctx.id and session_info.tmp.get('message_type') != 'group_direct':
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await ctx._api.post_group_file(
                            group_openid=ctx.group_openid,
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    send = await ctx.reply(
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                        message_reference=msg_quote,
                    )
                    # else:
                    #     md = MarkdownPayload(content=msg)
                    #     send = await ctx.reply(
                    #         markdown=md,
                    #         msg_type=2,
                    #         msg_seq=seq,
                    #         message_reference = msg_quote
                    #     )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        msg_ids.append(send["id"])
                        seq += 1
                    if images:
                        for img in images:
                            send_img = await ctx._api.post_group_file(
                                group_openid=ctx.group_openid,
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await ctx.reply(msg_type=7, media=send_img, msg_seq=seq)
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                            if send:
                                msg_ids.append(send["id"])
                                seq += 1
                    ctx.msg_seq = seq
                elif isinstance(ctx, C2CMessage):
                    seq = ctx.msg_seq if ctx.msg_seq else 1
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await ctx._api.post_c2c_file(
                            openid=ctx.author.user_openid,
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    msg = "" if not msg else msg
                    send = await ctx.reply(
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                    )
                    # else:
                    #     md = MarkdownPayload(content=msg)
                    #     send = await ctx.reply(
                    #         markdown=md,
                    #         msg_type=2,
                    #         msg_seq=seq,
                    #         message_reference = msg_quote
                    #     )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        msg_ids.append(send["id"])
                        seq += 1
                    if images:
                        for img in images:
                            send_img = await ctx._api.post_c2c_file(
                                openid=ctx.author.user_openid,
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await ctx.reply(msg_type=7, media=send_img, msg_seq=seq)
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                            if send:
                                msg_ids.append(send["id"])
                                seq += 1
                    ctx.msg_seq = seq
            else:
                from bots.qqbot.bot import client

                client.api = ModdedBotAPI(http=client.http)

                if session_info.target_from == target_guild_prefix:
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                    send_img = await image_1.get() if image_1 else None
                    msg = "" if not msg else msg
                    await client.api.post_message(
                        channel_id=session_info.get_common_target_id(),
                        content=msg,
                        file_image=send_img,
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if images:
                        for img in images:
                            send_img = await img.get()
                            await client.api.post_message(
                                channel_id=session_info.get_common_target_id(), file_image=send_img
                            )
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                elif session_info.target_from == target_direct_prefix:
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                    send_img = await image_1.get() if image_1 else None
                    msg = "" if not msg else msg
                    await client.api.post_dms(
                        guild_id=session_info.get_common_target_id(), content=msg, file_image=send_img
                    )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if images:
                        for img in images:
                            send_img = await img.get()
                            await client.api.post_dms(guild_id=session_info.get_common_target_id(), file_image=send_img)
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                elif session_info.target_from == target_group_prefix:
                    seq = 1

                    msg = "" if not msg else msg
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await client.api.post_group_file(
                            group_openid=session_info.get_common_target_id(),
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    send = await client.api.post_group_message(
                        group_openid=session_info.get_common_target_id(),
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                    )
                    # else:
                    #     md = MarkdownPayload(content=msg)
                    #     send = await ctx.reply(
                    #         markdown=md,
                    #         msg_type=2,
                    #         msg_seq=seq,
                    #     )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        seq += 1
                    if images:
                        for img in images:
                            send_img = await client.api.post_group_file(
                                group_openid=session_info.get_common_target_id(),
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await client.api.post_group_message(
                                group_openid=session_info.get_common_target_id(),
                                msg_type=7,
                                media=send_img,
                                msg_seq=seq,
                            )
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                            if send:
                                seq += 1
                elif session_info.target_from == target_c2c_prefix:
                    seq = 1
                    if images:
                        image_1 = images[0]
                        images.pop(0)
                        send_img = await client.api.post_c2c_file(
                            openid=session_info.get_common_target_id(),
                            file_type=1,
                            file_data=await image_1.get_base64(),
                        )
                    msg = "" if not msg else msg
                    send = await client.api.post_c2c_message(
                        openid=session_info.get_common_target_id(),
                        content=msg,
                        msg_type=7 if send_img else 0,
                        media=send_img,
                        msg_seq=seq,
                    )
                    # else:
                    #     md = MarkdownPayload(content=msg)
                    #     send = await ctx.reply(
                    #         markdown=md,
                    #         msg_type=2,
                    #         msg_seq=seq,
                    #     )
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: {msg.strip()}")
                    if image_1:
                        Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(image_1)}")
                    if send:
                        seq += 1
                    if images:
                        for img in images:
                            send_img = await client.api.post_c2c_file(
                                openid=session_info.get_common_target_id(),
                                file_type=1,
                                file_data=await img.get_base64(),
                            )
                            send = await client.api.post_c2c_message(
                                openid=session_info.get_common_target_id(), msg_type=7, media=send_img, msg_seq=seq
                            )
                            Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(img)}")
                            if send:
                                seq += 1

        return msg_ids

    @classmethod
    async def delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ) -> None:
        if isinstance(message_id, str):
            message_id = [message_id]
        if not isinstance(message_id, list):
            raise TypeError("Message ID must be a list or str")

        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")

        from bots.qqbot.bot import client

        client.api = ModdedBotAPI(http=client.http)
        if session_info.target_from == target_guild_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_message(
                        channel_id=session_info.get_common_target_id(), message_id=msg_id, hidetip=True
                    )
                    Logger.info(f"Deleted message {msg_id} in session {session_info.session_id}")
                except Exception:
                    Logger.exception(f"Failed to delete message {msg_id} in session {session_info.session_id}: ")
        elif session_info.target_from == target_group_prefix:
            for msg_id in message_id:
                try:
                    await client.api.recall_group_message(
                        group_openid=session_info.get_common_target_id(), message_id=msg_id
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

            from bots.qqbot.bot import client

            try:
                await client.api.put_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
                Logger.info(f'Added reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
            except Exception:
                Logger.exception(
                    f'Failed to add reaction "{emoji}" to message {message_id} in session {session_info.session_id}: '
                )

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

            from bots.qqbot.bot import client

            try:
                await client.api.delete_reaction(
                    channel_id=session_info.get_common_target_id(),
                    message_id=message_id[-1],
                    emoji_type=emoji_type,
                    emoji_id=emoji,
                )
                Logger.info(f'Removed reaction "{emoji}" to message {message_id} in session {session_info.session_id}')
            except Exception:
                Logger.exception(
                    f'Failed to remove reaction "{emoji}" to message {message_id} in session {
                        session_info.session_id
                    }: '
                )

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            Logger.debug(f"Start typing in session: {session_info.session_id}")

            if session_info.target_from == target_guild_prefix:
                emoji_type = 1 if int(qq_typing_emoji) < 9000 else 2

                from bots.qqbot.bot import client

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

            from bots.qqbot.bot import client

            await client.api.put_reaction(
                channel_id=session_info.get_common_target_id(),
                message_id=session_info.message_id,
                emoji_type=emoji_type,
                emoji_id=qq_limited_emoji,
            )


class QQBotFetchedContextManager(QQBotContextManager):
    pass
