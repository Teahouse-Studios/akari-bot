from core.builtins import Bot
from core.component import module
from .mcmod import mcmod as m

mcmod = module(
    bind_prefix="mcmod",
    desc="[I18N:mcmod.help.desc]",
    doc=True,
    developers=["Dianliang233", "HornCopper", "DrLee_lihr"],
    alias={"moddetails": "mcmod details"},
    support_languages=["zh_cn"],
)


@mcmod.command("<mod_name> {[I18N:mcmod.help.mod_name]}")
async def _(msg: Bot.MessageSession, mod_name: str):
    await msg.finish(await m(msg, mod_name))


@mcmod.command("details <content> {[I18N:mcmod.help.details]}")
async def _(msg: Bot.MessageSession, content: str):
    await msg.finish(await m(msg, content, detail=True))
