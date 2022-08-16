import traceback

import discord

from bots.discord.message import convert_embed
from config import Config
from core.builtins.message import MessageSession as MS
from core.elements import Plain, Image, FinishedSession as FinS
from core.elements.message.chain import MessageChain
from core.elements.message.internal import Embed
from core.logger import Logger

enable_analytics = Config('enable_analytics')


class FinishedSession(FinS):
    async def delete(self):
        """
        用于删除这条消息。
        """
        try:
            for x in self.result:
                await x.delete()
        except Exception:
            Logger.error(traceback.format_exc())


class MessageSession(MS):
    command = ''

    class Feature:
        image = True
        voice = False
        embed = True
        forward = False
        delete = True
        quote = False
        wait = True

    async def sendMessage(self, msgchain, quote=True, disable_secret_check=False) -> FinishedSession:
        msgchain = MessageChain(msgchain)
        if not msgchain.is_safe and not disable_secret_check:
            return await self.sendMessage('https://wdf.ink/6Oup')
        self.sent.append(msgchain)
        count = 0
        send = []
        for x in msgchain.asSendable():
            if isinstance(x, Plain):
                send_ = await self.session.message.respond(x.text)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: {x.text}')
            elif isinstance(x, Image):
                send_ = await self.session.message.respond(file=discord.File(await x.get()))
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Embed):
                embeds, files = await convert_embed(x)
                send_ = await self.session.message.respond(embed=embeds)
                Logger.info(f'[Bot] -> [{self.target.targetId}]: Embed: {str(x.__dict__)}')
            else:
                send_ = False
            if send_:
                send.append(send_)
            count += 1
        msgIds = []
        for x in send:
            msgIds.append(x.id)

        return FinishedSession(msgIds, send)

    async def checkPermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel) \
                or self.target.senderInfo.query.isSuperUser \
                or self.target.senderInfo.check_TargetAdmin(self.target.targetId):
            return True
        return False

    async def checkNativePermission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel):
            return True
        return False

    def asDisplay(self):
        return self.command

    async def delete(self):
        try:
            await self.session.message.delete()
        except Exception:
            Logger.error(traceback.format_exc())
