import os
import re
import sys

import botpy
from botpy.message import GroupMessage, Message

from bots.ntqq.info import *
from bots.ntqq.message import MessageSession
from core.bot import init_async, load_prompt
from core.builtins import EnableDirtyWordCheck, PrivateAssets, Url
from core.config import Config
from core.logger import Logger
from core.parser.message import parser
from core.path import assets_path
from core.types import MsgInfo, Session, FetchTarget
from core.utils.info import Info

PrivateAssets.set(os.path.join(assets_path, 'private', 'ntqq'))
EnableDirtyWordCheck.status = Config('enable_dirty_check', False)
Url.disable_mm = False
qq_appid = Config("qq_appid", cfg_type=str)
qq_secret = Config("qq_secret", cfg_type=str)


class MyClient(botpy.Client):
    async def on_ready(self):
        await init_async()
        await load_prompt(FetchTarget)

    async def on_at_message_create(self, message: Message):
        message.content = re.sub(r'<@(.*?)>', '', message.content).strip()
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_group_name}|{
                    message.guild_id}',
                sender_id=f'{sender_name}|{
                    message.guild_id}|{
                    message.author.id}',
                target_from=target_group_name,
                sender_from=f'{sender_name}|{message.guild_id}',
                sender_name=message.author.id,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{target_group_name}|{
                    message.guild_id}',
                sender=f'{
                    message.guild_id}|{
                    message.author.id}'))
        if message.content.startswith('/'):
            await parser(msg, prefix=['/'], require_enable_modules=False)
        await parser(msg)

    async def on_message_create(self, message: Message):
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_group_name}|{
                    message.guild_id}',
                sender_id=f'{sender_name}|{
                    message.guild_id}|{
                    message.author.id}',
                target_from=target_group_name,
                sender_from=f'{sender_name}|{message.guild_id}',
                sender_name=message.author.id,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{target_group_name}|{
                    message.guild_id}',
                sender=f'{
                    message.guild_id}|{
                    message.author.id}'))
        await parser(msg)

    async def on_group_at_message_create(self, message: GroupMessage):
        message.content = re.sub(r'<@(.*?)>', '', message.content).strip()
        reply_id = None
        if message.message_reference:
            reply_id = message.message_reference.message_id
        msg = MessageSession(
            MsgInfo(
                target_id=f'{target_group_name}|{
                    message.group_openid}',
                sender_id=f'{sender_name}|{
                    message.group_openid}|{
                    message.author.member_openid}',
                target_from=target_group_name,
                sender_from=f'{sender_name}|{message.group_openid}',
                sender_name=message.author.member_openid,
                client_name=client_name,
                message_id=message.id,
                reply_id=reply_id),
            Session(
                message=message,
                target=f'{target_group_name}|{
                    message.group_openid}',
                sender=f'{
                    message.group_openid}|{
                    message.author.member_openid}'))
        if message.content.startswith('/'):
            await parser(msg, prefix=['/'], require_enable_modules=False)
        await parser(msg)


intents = botpy.Intents(public_guild_messages=True, guild_messages=True, public_messages=True)
client = MyClient(intents=intents)

Info.client_name = client_name
if 'subprocess' in sys.argv:
    Info.subprocess = True

client.run(appid=qq_appid, secret=qq_secret)
