import os

import botpy

from config import Config
from core.builtins.message import MessageSession
from core.elements import MsgInfo, Session, StartUp, Schedule, EnableDirtyWordCheck, PrivateAssets
from core.elements.message.internal import Url
from core.utils import init, load_prompt, MessageTaskManager
from core.parser.message import parser


from bots.qqchannel.message import MessageSession

from botpy.message import Message

from core.logger import Logger

PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True
Url.mm = True
init()


class MyClient(botpy.Client):
    async def on_ready(self):
        Logger.info(f"robot 「{self.robot.name}」 on_ready!")

    async def on_at_message_create(self, message: Message):
        Logger.info(message.content)
        replyId = None
        if message.message_reference is not None:
            replyId = message.message_reference.message_id
        session = MessageSession(MsgInfo(targetId=f'QQChannel|{message.guild_id}|{message.channel_id}',
                                         senderId=f'QQChannelUser|{message.author.id}',
                                         targetFrom='QQChannel',
                                         senderFrom='QQChannelUser', senderName='', clientName='QQChannel',
                                         messageId=message.id,
                                         replyId=replyId),
                                 Session(message=message,
                                         target=f'{message.guild_id}|{message.channel_id}',
                                         sender=message.author.id))
        MessageTaskManager.check(session)
        await parser(session, require_enable_modules=False)


intents = botpy.Intents(public_guild_messages=True, direct_message=True)
client = MyClient(intents=intents)
client.run(appid=Config('qqchannel_appid'), token=Config('qqchannel_token'))
