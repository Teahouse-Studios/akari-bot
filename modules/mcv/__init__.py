from core.builtins import Bot
from core.component import module
from .mcv import mcjv, mcbv, mcdv, mcev, mclgv

m = module(
    "mcv",
    developers=["OasisAkari", "Dianliang233"],
    alias={
        "mcbv": "mcv mcbv",
        "mcdv": "mcv mcdv",
        "mcev": "mcv mcev",
        "mclgv": "mcv mclgv"
    },
    doc=True
)


@m.command("{{mcv.help.mcv}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcjv(msg))


@m.command("mcbv {{mcv.help.mcbv}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcbv(msg))


@m.command("mcdv {{mcv.help.mcdv}}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcdv(msg))


@m.command("mcev {{mcv.help.mcev}}")
async def mcev_loader(msg: Bot.MessageSession):
    await msg.finish(await mcev(msg))


@m.command("mclgv {{mcv.help.mclgv}}")
async def mclgv_loader(msg: Bot.MessageSession):
    await msg.finish(await mclgv(msg))
