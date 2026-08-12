import asyncio

import discord

from bots.discord.buttons import build_discord_button_view
from bots.discord.context import DiscordContextManager
from bots.discord.features import slash_features
from bots.discord.message_builder import build_discord_payloads
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.logger import Logger


class DiscordSlashContextManager(DiscordContextManager):
    context: dict[str, discord.ApplicationContext] = {}
    features: Features = slash_features
    typing_flags: dict[str, asyncio.Event] = {}

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ) -> list[str]:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        ctx: discord.ApplicationContext = cls.context[session_info.session_id]

        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        payloads = await build_discord_payloads(session_info, message, enable_parse_message)
        view = build_discord_button_view(
            payloads[-1].button_rows if payloads else [],
            session_info.sender_id,
            action_texts=payloads[-1].action_texts if payloads else [],
            modal_title=session_info.locale.t("message.action_text.modal.title"),
            input_label=session_info.locale.t("message.action_text.modal.input"),
            select_placeholder=session_info.locale.t("message.action_text.select"),
        )
        msg_ids = []
        for index, payload in enumerate(payloads):
            kwargs = {
                "content": payload.content,
                "files": payload.files or None,
                "embeds": payload.embeds or None,
                "view": view if index == len(payloads) - 1 else None,
            }
            send_ = await ctx.respond(**kwargs) if index == 0 else await ctx.send(**kwargs)
            if send_:
                msg_ids.append(str(send_.id))
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Aggregated Discord slash message {send_.id}")
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
