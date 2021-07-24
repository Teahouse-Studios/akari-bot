import traceback

import discord
from core.elements import Plain, Image, MessageSession
from core.bots.discord.client import client


class Template:
    all_func = ("sendMessage", "waitConfirm", "asDisplay", "revokeMessage", "Typing")

    async def sendMessage(self, msg: MessageSession, msgchain, Quote=True):
        if isinstance(msgchain, str):
            if msgchain == '':
                msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
            await msg.session.channel.send(msgchain, reference=msg.session if Quote else None)
        if isinstance(msgchain, list):
            count = 0
            for x in msgchain:
                if isinstance(x, Plain):
                    await msg.session.message.channel.send(x.text, reference=msg.session.message if Quote and count == 0 else None)
                if isinstance(x, Image):
                    await msg.session.message.channel.send(file=discord.File(x.image), reference=msg.session.message if Quote and count == 0 else None)
                count += 1

    async def waitConfirm(self, msg: MessageSession):
        confirm_command = ["是", "对", '确定', '是吧', '大概是',
                           '也许', '可能', '对的', '是呢', '对呢', '嗯', '嗯呢',
                           '吼啊', '资瓷', '是呗', '也许吧', '对呗', '应该',
                           'yes', 'y', 'yeah', 'yep', 'ok', 'okay', '⭐', '√']

        def check(m):
            return m.channel == msg.session.message.channel and m.author == msg.session.message.author

        msg = await client.wait_for('msg', check=check)
        return True if msg.content in confirm_command else False

    def asDisplay(self, msg: MessageSession):
        return msg.session.message.content

    async def revokeMessage(self, send_msg: discord.Message):
        try:
            await send_msg.delete()
        except:
            traceback.print_exc()

    class Typing:
        def __init__(self, msg: MessageSession):
            self.msg = msg

        async def __aenter__(self):
            async with self.msg.session.message.channel.typing() as typing:
                return typing

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass