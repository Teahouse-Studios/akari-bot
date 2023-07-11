import asyncio
import os
from tracemalloc import start
from bots.matrix import client

from bots.matrix.client import bot
import nio

from config import Config
from core.builtins import PrivateAssets, Url, EnableDirtyWordCheck
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import load_prompt, init_async
from bots.matrix.message import MessageSession, FetchTarget

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + "/assets"))
Url.disable_mm = True


async def on_sync(resp: nio.SyncResponse):
    with open(client.store_path_next_batch, 'w') as fp:
        fp.write(resp.next_batch)


async def on_invite(room: nio.MatrixRoom, event: nio.InviteEvent):
    Logger.info(f"Received Matrix room invitation for {room.room_id} ({room.name}) from {event.sender}")
    await bot.join(room.room_id)
    Logger.info(f"Joined Matrix room {room.room_id}")


async def on_message(room: nio.MatrixRoom, event: nio.RoomMessageFormatted):
    Logger.info(f"fmt: {event.format}, body: {event.body}, fmt body: {event.formatted_body}, sender: {event.sender}")
    # if message.channel_type.name == "GROUP":
    #    targetId = f"Kook|{message.channel_type.name}|{message.target_id}"
    # else:
    #    targetId = f"Kook|{message.channel_type.name}|{message.author_id}"
    # replyId = None
    # if "quote" in message.extra:
    #    replyId = message.extra["quote"]["rong_id"]

    # msg = MessageSession(
    #    MsgInfo(
    #        targetId=targetId,
    #        senderId=f"Kook|User|{message.author_id}",
    #        targetFrom=f"Kook|{message.channel_type.name}",
    #        senderFrom="Kook|User",
    #        senderName=message.author.nickname,
    #        clientName="Kook",
    #        messageId=message.id,
    #        replyId=replyId,
    #    ),
    #    Session(message=message, target=message.target_id, sender=message.author_id),
    # )
    # await parser(msg)


async def start():
    # Logger.info(f"trying first sync")
    # sync = await bot.sync()
    # Logger.info(f"first sync finished in {sync.elapsed}ms, dropped older messages")
    # if sync is nio.SyncError:
    #     Logger.error(f"failed in first sync: {sync.status_code} - {sync.message}")
    try:
        with open(client.store_path_next_batch, 'r') as fp:
            bot.next_batch = fp.read()
            Logger.info(f"loaded next sync batch from storage: {bot.next_batch}")
    except FileNotFoundError:
        bot.next_batch = 0

    bot.add_response_callback(on_sync, nio.SyncResponse)
    bot.add_event_callback(on_invite, nio.InviteEvent)
    bot.add_event_callback(on_message, nio.RoomMessageFormatted)

    await init_async()
    await load_prompt(FetchTarget)

    Logger.info(f"starting sync loop")
    await bot.sync_forever(timeout=30000, full_state=True, set_presence='online')
    Logger.error("? matrix-nio sync loop returned?")
    exit(1)

if bot:
    asyncio.run(start())
