import datetime

from core.builtins import Bot, Embed, EmbedField, Image
from core.component import module

t = module("embed_test", required_superuser=True, hidden=True)


@t.command()
async def _(msg: Bot.MessageSession):
    await msg.finish(
        Embed(
            title="Embed Test",
            description="This is a test embed.",
            url="https://zh.minecraft.wiki/wiki/Minecraft_Wiki",
            color=0x00FF00,
            timestamp=datetime.datetime.now().timestamp(),
            author="oasisakari",
            footer="Test",
            image=Image("https://avatars.githubusercontent.com/u/68471503?s=200&v=4"),
            fields=[
                EmbedField("oaoa", "aaaaa"),
                EmbedField("oaoa", "aaaaa", inline=True),
            ],
        )
    )
