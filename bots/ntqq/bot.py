import os
import re
import sys

import botpy
from botpy.message import C2CMessage, DirectMessage, GroupMessage, Message

from bots.ntqq.info import *
from bots.ntqq.message import MessageSession, FetchTarget
from core.bot import init_async, load_prompt
from core.builtins import EnableDirtyWordCheck, PrivateAssets, Url
from core.config import Config
from core.logger import Logger
from core.parser.message import parser
from core.path import assets_path
from core.types import MsgInfo, Session
from core.utils.info import Info

PrivateAssets.set(os.path.join(assets_path, 'private', 'ntqq'))
EnableDirtyWordCheck.status = Config('enable_dirty_check', False)
Url.disable_mm = False
qq_appid = str(Config("qq_bot_appid", cfg_type=(int, str)))
qq_secret = Config("qq_bot_secret", cfg_type=str)


class MyClient(botpy.Client):
    async def on_ready(self):
        await init_async()
        await load_prompt(FetchTarget)

    async def on_at_message_create(self, message: Message):
        message.content = re.sub(r'<@(.*?)>', '', message.content).strip()
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        prefix = None
        require_enable_modules = True
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_guild_name}|{message.guild_id}|{message.channel_id}',
                sender_id=f'{sender_name}|{message.author.id}',
                target_from=target_guild_name,
                sender_from=sender_name,
                sender_name=message.author.id,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{message.guild_id}|{message.channel_id}',
                sender=message.author.id))
        if not message.content:
            message.content = '/help'
        if message.content.strip().startswith('/'):
            prefix = ['/']
            require_enable_modules = False
        await parser(msg, prefix=prefix, require_enable_modules=require_enable_modules)

    async def on_message_create(self, message: Message):
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        prefix = None
        require_enable_modules = True
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_guild_name}|{message.guild_id}|{message.channel_id}',
                sender_id=f'{sender_name}|{message.author.id}',
                target_from=target_guild_name,
                sender_from=sender_name,
                sender_name=message.author.id,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{message.guild_id}|{message.channel_id}',
                sender=message.author.id))
        if message.content.strip().startswith('/'):
            prefix = ['/']
            require_enable_modules = False
        await parser(msg, prefix=prefix, require_enable_modules=require_enable_modules)

    async def on_group_at_message_create(self, message: GroupMessage):
        message.content = re.sub(r'<@(.*?)>', '', message.content).strip()
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        prefix = None
        require_enable_modules = True
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_group_name}|{message.group_openid}',
                sender_id=f'{sender_name}|{message.author.member_openid}',
                target_from=target_group_name,
                sender_from=sender_name,
                sender_name=message.author.member_openid,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=message.group_openid,
                sender=message.author.member_openid))
        if not message.content:
            message.content = '/help'
        if message.content.strip().startswith('/'):
            prefix = ['/']
            require_enable_modules = False
        await parser(msg, prefix=prefix, require_enable_modules=require_enable_modules)

    async def on_direct_message_create(self, message: DirectMessage):
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        prefix = None
        require_enable_modules = True
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_direct_name}|{message.guild_id}|{message.channel_id}',
                sender_id=f'{sender_name}|{message.author.id}',
                target_from=target_direct_name,
                sender_from=sender_name,
                sender_name=message.author.id,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{message.guild_id}|{message.channel_id}',
                sender=message.author.id))
        if message.content.strip().startswith('/'):
            prefix = ['/']
            require_enable_modules = False
        await parser(msg, prefix=prefix, require_enable_modules=require_enable_modules)

    async def on_c2c_message_create(self, message: C2CMessage):
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        prefix = None
        require_enable_modules = True
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_C2C_name}|{message.author.user_openid}',
                sender_id=f'{sender_name}|{message.author.user_openid}',
                target_from=target_C2C_name,
                sender_from=sender_name,
                sender_name=message.author.user_openid,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=message.author.user_openid,
                sender=message.author.user_openid))
        if message.content.strip().startswith('/'):
            prefix = ['/']
            require_enable_modules = False
        await parser(msg, prefix=prefix, require_enable_modules=require_enable_modules)


intents = botpy.Intents.none()
intents.public_guild_messages = True
intents.public_messages = True
if Config('qq_private_bot', False):
    intents.guild_messages = True

client = MyClient(intents=intents)

Info.client_name = client_name
if 'subprocess' in sys.argv:
    Info.subprocess = True

client.run(appid=qq_appid, secret=qq_secret)
