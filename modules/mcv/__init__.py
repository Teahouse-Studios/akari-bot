from core.builtins.bot import Bot
from core.component import module
from .mcv import mcjv, mcbv

m = module(
    "mcv",
    developers=["OasisAkari", "Dianliang233"],
    alias={
        "mcbv": "mcv mcbv",
        "mcev": "mcv mcev",
    },
    doc=True
)


@m.command("{{I18N:mcv.help.mcv}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcjv(msg))


@m.command("mcbv {{I18N:mcv.help.mcbv}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcbv(msg))

# @m.command("mcev {{I18N:mcv.help.mcev}}")
# async def mcev_loader(msg: Bot.MessageSession):
#     await msg.finish(await mcev(msg))
