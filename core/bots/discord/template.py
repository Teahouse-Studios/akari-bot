import discord
from core.elements import Plain, Image
from core.bots.discord.client import client


class Template:
    all_func = ("sendMessage", "waitConfirm", "asDisplay")

    async def sendMessage(self, message, msgchain, Quote=True):
        if isinstance(msgchain, str):
            if msgchain == '':
                msgchain = '发生错误：机器人尝试发送空文本消息，请联系机器人开发者解决问题。'
            await message['message'].channel.send(msgchain, reference=message['message'] if Quote else None)
        if isinstance(msgchain, list):
            count = 0
            for x in msgchain:
                if isinstance(x, Plain):
                    await message['message'].channel.send(x.text, reference=message['message'] if Quote and count == 0 else None)
                if isinstance(x, Image):
                    await message['message'].channel.send(file=discord.File(x.image), reference=message['message'] if Quote and count == 0 else None)
                count += 1

    async def waitConfirm(self, message):
        confirm_command = ["是", "对", '确定', '是吧', '大概是',
                           '也许', '可能', '对的', '是呢', '对呢', '嗯', '嗯呢',
                           '吼啊', '资瓷', '是呗', '也许吧', '对呗', '应该',
                           'yes', 'y', 'yeah', 'yep', 'ok', 'okay', '⭐', '√']

        def check(m):
            return m.channel == message['message'].channel and m.author == message['message'].author

        msg = await client.wait_for('message', check=check)
        return True if msg.content in confirm_command else False

    def asDisplay(self, message):
        return message['message'].content