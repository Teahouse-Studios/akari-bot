import datetime

from core.builtins import Bot, Embed, EmbedField, Image
from core.component import module

t = module('embed_test', required_superuser=True)


@t.handle()
async def _(msg: Bot.MessageSession):
    await msg.finish(Embed(title='Embed Test', description='This is a test embed.',
                                     url='https://minecraft.fandom.com/zh/wiki/Minecraft_Wiki',
                                     color=0x00ff00, timestamp=datetime.datetime.now().timestamp(),
                                     author='oasisakari',
                                     footer='Test',
                                     image=Image('https://http.cat/200'),
                                     fields=[EmbedField('oaoa', 'aaaaa'),
                                             EmbedField('oaoa', 'aaaaa', inline=True)]))
