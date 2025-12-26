import asyncio

from aiogram import types
from aiogram.enums import MessageEntityType

from bots.aiogram.client import dp, aiogram_bot, token
from bots.aiogram.context import AiogramContextManager, AiogramFetchedContextManager
from bots.aiogram.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Voice, Image, Plain
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.client.init import client_init
from core.config import Config
from core.constants.default import ignored_sender_default
from core.utils.http import download

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(AiogramContextManager)
Bot.register_context_manager(AiogramFetchedContextManager, fetch_session=True)

ignored_sender = Config("ignored_sender", ignored_sender_default)
mention_required = Config("mention_required", False)


async def to_message_chain(msg: types.Message):
    lst = []
    if msg.audio:
        file = await aiogram_bot.get_file(msg.audio.file_id)
        d = await download(
            f"https://api.telegram.org/file/bot{token}/{file.file_path}"
        )
        lst.append(Voice(d))
    if msg.photo:
        file = await aiogram_bot.get_file(msg.photo[-1]["file_id"])
        lst.append(
            Image(f"https://api.telegram.org/file/bot{token}/{file.file_path}")
        )
    if msg.voice:
        file = await aiogram_bot.get_file(msg.voice.file_id)
        d = await download(
            f"https://api.telegram.org/file/bot{token}/{file.file_path}"
        )
        lst.append(Voice(d))
    if msg.caption:
        lst.append(Plain(msg.caption))
    if msg.text:
        lst.append(Plain(msg.text))
    return MessageChain.assign(lst)


@dp.message()
async def msg_handler(message: types.Message):
    target_from = f"{target_prefix}|{message.chat.type.title()}"
    target_id = f"{target_from}|{message.chat.id}"
    sender_id = f"{sender_prefix}|{message.from_user.id}"
    if sender_id in ignored_sender:
        return

    reply_id = None
    if message.reply_to_message:
        reply_id = message.reply_to_message.message_id

    text = message.text or ""
    at_message = False
    entities = message.entities or []

    if entities and entities[0].offset == 0:
        first = entities[0]
        if first.type == MessageEntityType.TEXT_MENTION:
            bot_id = (await message.bot.get_me()).id
            if first.user.id != bot_id:
                return

            at_message = True
            text = text[first.length:].strip()

        elif first.type == MessageEntityType.MENTION:
            bot_username = (await message.bot.get_me()).username
            mention_text = text[:first.length]
            if mention_text != f"@{bot_username}":
                return

            at_message = True
            text = text[first.length:].strip()
        else:
            pass

        if at_message and not text:
            text = f"{command_prefix[0]}help"

    if mention_required and not at_message and message.chat.type != "private":
        return

    processed_message = message.model_copy(update={"text": text})
    msg_chain = await to_message_chain(processed_message)

    session = await SessionInfo.assign(target_id=target_id,
                                       sender_id=sender_id,
                                       sender_name=message.from_user.username,
                                       target_from=target_from,
                                       sender_from=sender_prefix,
                                       client_name=client_name,
                                       message_id=str(message.message_id),
                                       reply_id=reply_id,
                                       messages=msg_chain,
                                       ctx_slot=ctx_id
                                       )

    await Bot.process_message(session, message)


async def on_startup():
    await client_init(target_prefix_list, sender_prefix_list)


if Config("enable", False, table_name="bot_aiogram"):
    dp.startup.register(on_startup)
    asyncio.run(dp.start_polling(aiogram_bot))
