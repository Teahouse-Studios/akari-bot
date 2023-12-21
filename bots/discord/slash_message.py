import traceback

import discord

from bots.discord.message import convert_embed
from config import Config
from core.builtins import Plain, Image, MessageSession as MessageSessionT, MessageTaskManager
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Embed, ErrorMessage
from core.logger import Logger
from core.types import FinishedSession as FinS

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


class MessageSession(MessageSessionT):
    command = ''

    class Feature:
        image = True
        voice = False
        embed = True
        forward = False
        delete = True
        quote = False
        wait = True

    async def send_message(self, message_chain, quote=True, disable_secret_check=False, allow_split_image=True,
                           callback=None
                           ) -> FinishedSession:
        message_chain = MessageChain(message_chain)
        if not message_chain.is_safe and not disable_secret_check:
            return await self.send_message(Plain(ErrorMessage(self.locale.t("error.message.chain.unsafe"))))
        self.sent.append(message_chain)
        count = 0
        send = []
        first_send = True
        for x in message_chain.as_sendable(self):
            if isinstance(x, Plain):
                if first_send:
                    send_ = await self.session.message.respond(x.text)
                else:
                    send_ = await self.session.message.send(x.text)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: {x.text}')
            elif isinstance(x, Image):
                if first_send:
                    send_ = await self.session.message.respond(file=discord.File(await x.get()))
                else:
                    send_ = await self.session.message.send(file=discord.File(await x.get()))
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Image: {str(x.__dict__)}')
            elif isinstance(x, Embed):
                embeds, files = await convert_embed(x)
                if first_send:
                    send_ = await self.session.message.respond(embed=embeds)
                else:
                    send_ = await self.session.message.send(embed=embeds)
                Logger.info(f'[Bot] -> [{self.target.target_id}]: Embed: {str(x.__dict__)}')
            else:
                send_ = None
            if send_:
                send.append(send_)
            count += 1
            first_send = False
        msg_ids = []
        for x in send:
            msg_ids.append(x.id)
            if callback:
                MessageTaskManager.add_callback(x.id, callback)

        return FinishedSession(self, msg_ids, send)

    async def check_permission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel) \
                or self.target.sender_info.query.isSuperUser \
                or self.target.sender_info.check_TargetAdmin(self.target.target_id):
            return True
        return False

    async def check_native_permission(self):
        if self.session.message.channel.permissions_for(self.session.message.author).administrator \
                or isinstance(self.session.message.channel, discord.DMChannel):
            return True
        return False

    def as_display(self, text_only=False):
        return self.command

    sendMessage = send_message
    asDisplay = as_display
    checkNativePermission = check_native_permission

    async def delete(self):
        try:
            await self.session.message.delete()
        except Exception:
            Logger.error(traceback.format_exc())
