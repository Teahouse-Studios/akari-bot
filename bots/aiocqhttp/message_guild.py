import asyncio
import html
import re
from pathlib import Path

from aiocqhttp import MessageSegment

from bots.aiocqhttp.client import bot
from core.builtins import Plain, Image, ExecutionLockList, MessageSession as MS
from core.builtins.message.chain import MessageChain
from core.logger import Logger
from core.types import FinishedSession as FinS


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        ...


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
        embed = False
        forward = False
        delete = False
        wait = True
        quote = False

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False,
                          allow_split_image=True) -> FinishedSession:
        msg = MessageSegment.text('')
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage('https://wdf.ink/6Oup')
        self.sent.append(msgchain)
        count = 0
        for x in msgchain.asSendable(embed=False):
            if isinstance(x, Plain):
                msg = msg + MessageSegment.text(('\n' if count != 0 else '') + x.text)
            elif isinstance(x, Image):
                msg = msg + MessageSegment.image(Path(await x.get()).as_uri())
            # elif isinstance(x, Voice):
            #    msg = msg + MessageSegment.record(Path(x.path).as_uri())
            count += 1
        Logger.info(f'[Bot] -> [{self.target.targetId}]: {msg}')
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        send = await bot.call_action('send_guild_channel_msg', guild_id=int(match_guild.group(1)),
                                     channel_id=int(match_guild.group(2)), message=msg)

        return FinishedSession(send['message_id'], [send])

    async def checkPermission(self):
        if self.target.senderId in self.custom_admins or self.target.senderInfo.query.isSuperUser:
            return True
        return await self.checkNativePermission()

    async def checkNativePermission(self):
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        get_member_info = await bot.call_action('get_guild_member_profile', guild_id=match_guild.group(1),
                                                user_id=self.session.sender)
        print(get_member_info)
        for m in get_member_info['roles']:
            if m['role_id'] == "2":
                return True
        get_guild_info = await bot.call_action('get_guild_meta_by_guest', guild_id=match_guild.group(1))
        if get_guild_info['owner_id'] == self.session.sender:
            return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    async def get_text_channel_list(self):
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        get_channels_info = await bot.call_action('get_guild_channel_list', guild_id=match_guild.group(1),
                                                  no_cache=True)
        lst = []
        for m in get_channels_info:
            if m['channel_type'] == 1:
                lst.append(f'{m["owner_guild_id"]}|{m["channel_id"]}')
        return lst

    def asDisplay(self):
        return html.unescape(self.session.message.message)

    async def sleep(self, s):
        ExecutionLockList.remove(self)
        await asyncio.sleep(s)

    async def delete(self):
        """try:
            if isinstance(self.session.message, list):
                for x in self.session.message:
                    await bot.call_action('delete_msg', message_id=x['message_id'])
            else:
                print(self.session.message)
                await bot.call_action('delete_msg', message_id=self.session.message['message_id'])
        except Exception:
            traceback.print_exc()
        """

    class Typing:
        def __init__(self, msg: MS):
            self.msg = msg

        async def __aenter__(self):
            pass

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass


"""

class FetchTarget(FT):
    @staticmethod
    async def fetch_target(targetId) -> MessageSession:
        matchTarget = re.match(r'^QQ\|Guild\|(.*\|.*)', targetId)
        if matchTarget:
            return MessageSession(MsgInfo(targetId=targetId, senderId=targetId, senderName='',
                                          targetFrom='QQ|Guild', senderFrom='QQ|Guild'),
                                  Session(message=False, target=matchTarget.group(1),
                                          sender=matchTarget.group(1)))
        else:
            return False

    @staticmethod
    async def fetch_target_list(targetList: list) -> List[MessageSession]:
        lst = []
        guild_list_raw = await bot.call_action('get_guild_list')
        guild_list = []
        for g in guild_list_raw:
            get_channel_list = await bot.call_action('get_guild_channel_list', guild_id=g['guild_id'])
            for channel in get_channel_list:
                if channel['channel_type'] == 1:
                    guild_list.append(f"{str(g['guild_id'])}|{str(channel['channel_id'])}")
        for x in targetList:
            fet = await FetchTarget.fetch_target(x)
            if fet:
                if fet.session.target not in guild_list:
                    continue
                lst.append(fet)
        return lst

    @staticmethod
    async def post_message(module_name, message, user_list: List[MessageSession] = None):
        send_list = []
        if user_list is not None:
            for x in user_list:
                try:
                    send = await x.sendMessage(message, quote=False)
                    send_list.append(send)
                except Exception:
                    traceback.print_exc()
        else:
            get_target_id = BotDBUtil.Module.get_enabled_this(module_name)
            guild_list_raw = await bot.call_action('get_guild_list')
            guild_list = []
            for g in guild_list_raw:
                get_channel_list = await bot.call_action('get_guild_channel_list', guild_id=g['guild_id'])
                for channel in get_channel_list:
                    if channel['channel_type'] == 1:
                        guild_list.append(f"{str(g['guild_id'])}|{str(channel['channel_id'])}")
            for x in get_target_id:
                fetch = await FetchTarget.fetch_target(x)
                if fetch:
                    if fetch.session.target not in guild_list:
                        continue
                    try:
                        send = await fetch.sendMessage(message, quote=False)
                        send_list.append(send)
                        await asyncio.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
        return send_list
"""
