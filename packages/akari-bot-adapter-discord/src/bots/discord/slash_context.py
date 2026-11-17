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
    typing_tasks: dict[str, asyncio.Task[None]] = {}
    TYPING_MAX_LIFETIME = 60

    @classmethod
    async def send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
    ) -> list[str]:
        msg_ids = []
        try:
            return await cls._send_message(
                session_info,
                message,
                quote=quote,
                msg_ids=msg_ids,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            Logger.exception(f"Failed to send Discord slash message to {session_info.target_id}: ")
            return msg_ids

    @classmethod
    async def _send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        msg_ids: list[str] | None = None,
    ) -> list[str]:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        ctx: discord.ApplicationContext = cls.context[session_info.session_id]

        if isinstance(message, MessageNodes):
            Logger.error("This session does not support message nodes, check if bug exists.")
            return []

        payloads = await build_discord_payloads(session_info, message)
        view = build_discord_button_view(
            payloads[-1].button_rows if payloads else [],
            session_info.sender_id,
            action_texts=payloads[-1].action_texts if payloads else [],
            modal_title=session_info.locale.t("message.action_text.modal.title"),
            input_label=session_info.locale.t("message.action_text.modal.input"),
            select_placeholder=session_info.locale.t("message.action_text.select"),
        )
        if msg_ids is None:
            msg_ids = []
        for index, payload in enumerate(payloads):
            kwargs = {
                "content": payload.content,
                "files": payload.files or None,
                "embeds": payload.embeds or None,
                "view": view if index == len(payloads) - 1 else None,
            }
            send_ = await ctx.respond(**kwargs) if index == 0 else await ctx.send(**kwargs)
            # py-cord 的首次 Interaction 响应返回 Interaction 本身，其 id 是交互 ID，
            # 不能用于撤回、Callback 或后续消息操作。后续响应则直接返回 WebhookMessage。
            if isinstance(send_, discord.Interaction):
                send_ = await send_.original_response()
            if send_:
                msg_ids.append(str(send_.id))
            Logger.info(f"[Bot] -> [{session_info.target_id}]: Aggregated Discord slash message {send_.id}")
        return msg_ids

    @classmethod
    async def start_typing(cls, session_info: SessionInfo) -> None:
        if session_info.session_id not in cls.context:
            raise ValueError("Session not found in context")
        previous = cls.typing_flags.pop(session_info.session_id, None)
        if previous:
            previous.set()
        previous_task = cls.typing_tasks.pop(session_info.session_id, None)
        if previous_task:
            previous_task.cancel()
            await asyncio.gather(previous_task, return_exceptions=True)
        flag = asyncio.Event()
        cls.typing_flags[session_info.session_id] = flag

        async def _typing():
            try:
                async with asyncio.timeout(cls.TYPING_MAX_LIFETIME):
                    ctx: discord.ApplicationContext | None = cls.context.get(session_info.session_id)
                    if not ctx:
                        return
                    async with ctx.channel.typing():
                        await ctx.defer()
                        Logger.debug(f"Start typing in session: {session_info.session_id}")
                        await flag.wait()
            except TimeoutError:
                Logger.debug(f"Typing state expired in session: {session_info.session_id}")
            except Exception:
                Logger.exception(f"Failed to start typing in session {session_info.session_id}: ")
            finally:
                if cls.typing_flags.get(session_info.session_id) is flag:
                    cls.typing_flags.pop(session_info.session_id, None)
                current_task = asyncio.current_task()
                if cls.typing_tasks.get(session_info.session_id) is current_task:
                    cls.typing_tasks.pop(session_info.session_id, None)

        cls.typing_tasks[session_info.session_id] = asyncio.create_task(
            _typing(), name=f"discord-slash-typing-{session_info.session_id}"
        )

    @classmethod
    async def end_typing(cls, session_info: SessionInfo) -> None:
        # if session_info.session_id not in cls.context:
        #     raise ValueError("Session not found in context")
        flag = cls.typing_flags.pop(session_info.session_id, None)
        if flag:
            flag.set()
        task = cls.typing_tasks.pop(session_info.session_id, None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if flag:
            Logger.debug(f"End typing in session: {session_info.session_id}")
