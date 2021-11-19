import asyncio
import html
import re
from pathlib import Path

from aiocqhttp import MessageSegment

from core.bots.aiocqhttp.client import bot
from core.bots.aiocqhttp.tasks import MessageTaskManager, FinishedTasks
from core.elements import Plain, Image, MessageSession as MS, MsgInfo, Session, ExecutionLockList
from core.elements.others import confirm_command
from core.logger import Logger
from core.secret_check import Secret


def convert2lst(s) -> list:
    if isinstance(s, str):
        return [Plain(s)]
    elif isinstance(s, list):
        return s
    elif isinstance(s, tuple):
        return list(s)


class MessageSession(MS):
    class Feature:
        image = True
        voice = False
        forward = False
        delete = False

    async def sendMessage(self, msgchain, quote=True):
        msg = MessageSegment.text('')
        # if quote:
        #    msg = MessageSegment.reply(self.session.message.message_id)
        if Secret.find(msgchain):
            return await self.sendMessage('https://wdf.ink/6Oup')
        if isinstance(msgchain, str):
            msg = msg + (MessageSegment.text(msgchain if msgchain != '' else
                                             '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
                                             '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title='))
        elif isinstance(msgchain, (list, tuple)):
            count = 0
            for x in msgchain:
                if isinstance(x, Plain):
                    msg = msg + MessageSegment.text(('\n' if count != 0 else '') + x.text)
                elif isinstance(x, Image):
                    msg = msg + MessageSegment.image(Path(await x.get()).as_uri())
                # elif isinstance(x, Voice):
                #    msg = msg + MessageSegment.record(Path(x.path).as_uri())
                count += 1
        else:
            msg = msg + MessageSegment.text('发生错误：机器人尝试发送非法消息链，请联系机器人开发者解决问题。'
                                            '\n错误汇报地址：https://github.com/Teahouse-Studios/bot/issues/new?assignees=OasisAkari&labels=bug&template=5678.md&title=')
        Logger.info(f'[Bot] -> [{self.target.targetId}]: {msg}')
        Logger.info(self.session.target)
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        send = await bot.call_action('send_guild_channel_msg', guild_id=int(match_guild.group(1)),
                                     channel_id=int(match_guild.group(2)), message=msg)

        return MessageSession(target=MsgInfo(targetId=0, senderId=0, senderName='', targetFrom='QQ|Bot',
                                             senderFrom='QQ|Bot'),
                              session=Session(message=send,
                                              target=self.session.target,
                                              sender=self.session.sender))

    async def waitConfirm(self, msgchain=None, quote=True):
        send = None
        ExecutionLockList.remove(self)
        if msgchain is not None:
            msgchain = convert2lst(msgchain)
            msgchain.append(Plain('（发送“是”或符合确认条件的词语来确认）'))
            send = await self.sendMessage(msgchain, quote)
        flag = asyncio.Event()
        MessageTaskManager.add_guild_task(self.session.sender, flag)
        await flag.wait()
        if send is not None:
            await send.delete()
        if FinishedTasks.guild_get()[self.session.sender] in confirm_command:
            return True
        return False

    async def checkPermission(self):
        if self.target.senderInfo.check_TargetAdmin(self.target.targetId) or self.target.senderInfo.query.isSuperUser:
            return True
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        get_member_info = await bot.call_action('get_guild_members', guild_id=match_guild.group(1))
        tiny_id = self.session.sender
        for m in get_member_info['admins']:
            if m['tiny_id'] == tiny_id:
                return True
        return False

    def checkSuperUser(self):
        return True if self.target.senderInfo.query.isSuperUser else False

    async def get_text_channel_list(self):
        match_guild = re.match(r'(.*)\|(.*)', self.session.target)
        get_channels_info = await bot.call_action('get_guild_channel_list', guild_id=match_guild.group(1), no_cache=True)
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