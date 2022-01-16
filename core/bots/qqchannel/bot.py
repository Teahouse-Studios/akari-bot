import asyncio
import os
import re

import qqbot

from config import Config
from core.elements import MsgInfo, Session, StartUp, Schedule, EnableDirtyWordCheck, PrivateAssets
from core.loader import ModulesManager
from core.parser.message import parser
from core.scheduler import Scheduler
from core.utils import init, load_prompt
from database import BotDBUtil

from core.bots.qqchannel.token import token
from core.bots.qqchannel.message import MessageSession


PrivateAssets.set(os.path.abspath(os.path.dirname(__file__) + '/assets'))
EnableDirtyWordCheck.status = True
init()


async def _message_handler(event, message: qqbot.Message):
    """
    定义事件回调的处理
    :param event: 事件类型
    :param message: 事件对象（如监听消息是Message对象）
    """
    msg_api = qqbot.AsyncMessageAPI(token, False)
    # 打印返回信息
    qqbot.logger.info("event %s" % event + ",receive message %s" % message.content)
    message.content = re.sub(r'^<.*?>', '', message.content)
    print(message.content)
    msg = MessageSession(MsgInfo(targetId=f'QQ|GuildO|{message.guild_id}|{message.channel_id}',
                                 senderId=f'QQ|GuildO|Author|{message.author.id}',
                                 targetFrom='QQ|GuildO',
                                 senderFrom='QQ|GuildO|Author', senderName=''),
                         Session(message=message,
                                 target=f'{message.guild_id}|{message.channel_id}',
                                 sender=message.author.id))
    await parser(msg, require_enable_modules=False)

qqbot_handler = qqbot.Handler(
    qqbot.HandlerType.AT_MESSAGE_EVENT_HANDLER, _message_handler
)
qqbot.async_listen_events(token, False, qqbot_handler)
