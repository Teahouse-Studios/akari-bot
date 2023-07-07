import os

from bots.kook.client import bot
from khl import Message, MessageTypes

from config import Config
from core.builtins import PrivateAssets, Url, EnableDirtyWordCheck
from core.logger import Logger
from core.parser.message import parser
from core.types import MsgInfo, Session
from core.utils.bot import load_prompt, init_async
from bots.kook.message import MessageSession, FetchTarget

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True if Config('enable_dirty_check') else False
Url.disable_mm = False if Config('enable_urlmanager') else True
Url.md_format = True


@bot.on_message((MessageTypes.TEXT, MessageTypes.IMG))
async def msg_handler(message: Message):
    if message.channel_type.name == "GROUP":
        targetId = f'Kook|{message.channel_type.name}|{message.target_id}'
    else:
        targetId = f'Kook|{message.channel_type.name}|{message.author_id}'
    replyId = None
    if 'quote' in message.extra:
        replyId = message.extra['quote']['rong_id']

    msg = MessageSession(MsgInfo(targetId=targetId,
                                 senderId=f'Kook|User|{message.author_id}',
                                 targetFrom=f'Kook|{message.channel_type.name}',
                                 senderFrom='Kook|User', senderName=message.author.nickname,
                                 clientName='Kook',
                                 messageId=message.id,
                                 replyId=replyId),
                         Session(message=message, target=message.target_id, sender=message.author_id))
    await parser(msg)


@bot.on_startup
async def _(b: bot):
    await init_async()
    await load_prompt(FetchTarget)


if bot:
    bot.run()
