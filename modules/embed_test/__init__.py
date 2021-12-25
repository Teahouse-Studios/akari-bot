import datetime

from core.elements import MessageSession, Embed, Image, EmbedField
from core.component import on_command

t = on_command('embed_test', required_superuser=True)


@t.handle()
async def _(session: MessageSession):
    await session.sendMessage(Embed(title='Embed Test', description='This is a test embed.',
                                    url='https://minecraft.fandom.com/zh/wiki/Minecraft_Wiki',
                                    color=0x00ff00, timestamp=datetime.datetime.now().timestamp(),
                                    author='oasisakari',
                                    footer='Test',
                                    fields=[EmbedField('oaoa', 'aaaaa', inline=True),
                                            EmbedField('oaoa', 'aaaaa', inline=True)]))
