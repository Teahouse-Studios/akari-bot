import datetime
import traceback

from core.builtins import Bot, Embed, Image, EmbedField, Plain
from core.component import on_command
from core.exceptions import InvalidHelpDocTypeError
from core.extra import pir
from core.loader import ModulesManager
from core.parser.command import CommandParser
from core.types import Command
from core.utils.image_table import ImageTable, image_table_render
from database import BotDBUtil

t = on_command('embed_test', required_superuser=True)


@t.handle()
async def _(session: Bot.MessageSession):
    await session.sendMessage(Embed(title='Embed Test', description='This is a test embed.',
                                    url='https://minecraft.fandom.com/zh/wiki/Minecraft_Wiki',
                                    color=0x00ff00, timestamp=datetime.datetime.now().timestamp(),
                                    author='oasisakari',
                                    footer='Test',
                                    image=Image('https://avatars.githubusercontent.com/u/68471503?s=200&v=4'),
                                    fields=[EmbedField('oaoa', 'aaaaa', inline=True),
                                            EmbedField('oaoa', 'aaaaa', inline=True)]))


@t.handle('new_help {测试罢了}')
async def __(msg: Bot.MessageSession):
    module_list = ModulesManager.return_modules_list_as_dict(
        targetFrom=msg.target.targetFrom)
    msg.sendMessage(module_list)
