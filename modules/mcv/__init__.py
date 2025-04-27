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


@m.command("{[I18N:mcv.help.mcv]}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcjv(msg))


@m.command("mcbv {[I18N:mcv.help.mcbv]}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcbv(msg))


@m.command("mcdv {[I18N:mcv.help.mcdv]}")
async def _(msg: Bot.MessageSession):
    await msg.finish(await mcdv(msg))


@m.command("mcev {[I18N:mcv.help.mcev]}")
async def mcev_loader(msg: Bot.MessageSession):
    await msg.finish(await mcev(msg))


@m.command("mclgv {[I18N:mcv.help.mclgv]}")
async def mclgv_loader(msg: Bot.MessageSession):
    await msg.finish(await mclgv(msg))
