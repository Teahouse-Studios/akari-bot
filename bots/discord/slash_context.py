import asyncio

import discord

from bots.discord.context import DiscordContextManager
from bots.discord.features import Features
from bots.discord.info import client_name, target_channel_prefix
from bots.discord.utils import convert_embed
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement, ImageElement, VoiceElement, MentionElement, EmbedElement
from core.builtins.session.info import SessionInfo
from core.logger import Logger


class DiscordSlashContextManager(DiscordContextManager):
    context: dict[str, discord.ApplicationContext] = {}
    features: Features | None = Features
    typing_flags: dict[str, asyncio.Event] = {}

    @classmethod
    async def send_message(cls, session_info: SessionInfo, message: MessageChain, quote: bool = True,
                           enable_parse_message: bool = True,
                           enable_split_image: bool = True, ):
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        ctx: discord.ApplicationContext = cls.context.get(session_info.session_id)

        count = 0
        msg_ids = []
        for x in message.as_sendable(session_info, parse_message=enable_parse_message):
            send_ = None
            if isinstance(x, PlainElement):
                if count == 0:
                    send_ = await ctx.respond(x.text)
                else:
                    send_ = await ctx.send(x.text)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: {x.text}")
            elif isinstance(x, ImageElement):
                if count == 0:
                    send_ = await ctx.respond(
                        file=discord.File(await x.get())
                    )
                else:
                    send_ = await ctx.send(
                        file=discord.File(await x.get())
                    )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Image: {str(x)}")
            elif isinstance(x, VoiceElement):
                if count == 0:
                    send_ = await ctx.respond(
                        file=discord.File(x.path)
                    )
                else:
                    send_ = await ctx.send(
                        file=discord.File(x.path)
                    )
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Voice: {str(x)}")
            elif isinstance(x, MentionElement):
                if x.client == client_name and session_info.target_from == target_channel_prefix:
                    if count == 0:
                        send_ = await ctx.respond(f"<@{x.id}>")
                    else:
                        send_ = await ctx.send(f"<@{x.id}>")
                    Logger.info(f"[Bot] -> [{session_info.target_id}]: Mention: {x.client}|{str(x.id)}")
            elif isinstance(x, EmbedElement):
                embeds, files = await convert_embed(x, session_info)
                if count == 0:
                    send_ = await ctx.respond(
                        embed=embeds,
                        files=files)
                else:
                    send_ = await ctx.send(
                        embed=embeds,
                        files=files)
                Logger.info(f"[Bot] -> [{session_info.target_id}]: Embed: {str(x)}")

            if send_:
                msg_ids.append(str(send_.id))
            count += 1
        return msg_ids

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        async def _typing():
            if session_info.session_id not in cls.context:
                raise ValueError("Session not found in context")
            ctx: discord.ApplicationContext = cls.context[session_info.session_id]
            if ctx:
                async with ctx.channel.typing():
                    await ctx.defer()
                    Logger.debug(f"Start typing in session: {session_info.session_id}")
                    # 这里可以添加开始输入状态的逻辑
                    flag = asyncio.Event()
                    cls.typing_flags[session_info.session_id] = flag
                    await flag.wait()

            # 这里可以添加开始输入状态的逻辑

        asyncio.create_task(_typing())

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        if session_info.session_id in cls.typing_flags:
            cls.typing_flags[session_info.session_id].set()
            del cls.typing_flags[session_info.session_id]
            Logger.debug(f"End typing in session: {session_info.session_id}")
