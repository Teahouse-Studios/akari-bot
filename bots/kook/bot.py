import asyncio
import os
import sys

from khl import Message, MessageTypes

sys.path.append(os.getcwd())

from bots.kook.client import bot  # noqa: E402
from bots.kook.info import *  # noqa: E402
from bots.kook.message import MessageSession, FetchTarget  # noqa: E402
from core.bot_init import load_prompt, init_async  # noqa: E402
from core.builtins import Info, PrivateAssets  # noqa: E402
from core.config import Config  # noqa: E402
from core.constants.default import ignored_sender_default  # noqa: E402
from core.constants.path import assets_path  # noqa: E402
from core.parser.message import parser  # noqa: E402
from core.terminate import cleanup_sessions  # noqa: E402
from core.types import MsgInfo, Session  # noqa: E402

Info.dirty_word_check = Config("enable_dirty_check", False)
Info.use_url_manager = Config("enable_urlmanager", False)
Info.use_url_md_format = True
PrivateAssets.set(os.path.join(assets_path, "private", "kook"))
ignored_sender = Config("ignored_sender", ignored_sender_default)


@bot.on_message((MessageTypes.TEXT, MessageTypes.IMG))
async def msg_handler(message: Message):
    if message.channel_type.name == "GROUP":
        target_id = f"{target_group_prefix}|{message.target_id}"
    else:
        target_id = f"{target_person_prefix}|{message.author_id}"
    sender_id = f"{sender_prefix}|{message.author_id}"
    if sender_id in ignored_sender:
        return

    reply_id = None
    if "quote" in message.extra:
        reply_id = message.extra["quote"]["rong_id"]

    target = f"{target_prefix}|{message.channel_type.name.title()}"

    msg = MessageSession(
        MsgInfo(
            target_id=target_id,
            sender_id=sender_id,
            target_from=target,
            sender_from=sender_prefix,
            sender_name=message.author.nickname,
            client_name=client_name,
            message_id=message.id,
            reply_id=reply_id,
        ),
        Session(message=message, target=message.target_id, sender=message.author_id),
    )
    await parser(msg)


@bot.on_startup
async def _(b: bot):
    await init_async()
    await load_prompt(FetchTarget)


if Config("enable", False, table_name="bot_kook") or __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        Info.client_name = client_name
        if "subprocess" in sys.argv:
            Info.subprocess = True

        loop.run_until_complete(bot.start())
    except (KeyboardInterrupt, SystemExit):
        loop.run_until_complete(cleanup_sessions())
