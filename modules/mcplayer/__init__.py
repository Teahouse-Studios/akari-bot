from core.builtins import Bot, I18NContext, Image, Plain, Url
from core.component import module
from .mojang_api import *

mcplayer = module(
    bind_prefix="mcplayer",
    desc="{I18N:mcplayer.help.desc}",
    doc=True,
    developers=["Dianliang233"],
)


@mcplayer.command("<username_or_uuid> {{I18N:mcplayer.help}}")
async def _(msg: Bot.MessageSession, username_or_uuid: str):
    arg = username_or_uuid
    try:
        if len(arg) == 32:
            name = await uuid_to_name(arg)
            uuid = arg
        elif len(arg) == 36 and arg.count("-") == 4:
            uuid = arg.replace("-", "")
            name = await uuid_to_name(arg)
        else:
            name = arg
            uuid = await name_to_uuid(arg)
        namemc = f"https://namemc.com/profile/{name}"
        sac = await uuid_to_skin_and_cape(uuid)
        if sac:
            render = sac["render"]
            skin = sac["skin"]
            cape = sac["cape"]
            chain = [Plain(f"{name} ({uuid})"), Url(namemc), Image(render), Image(skin)]
            if cape:
                chain.append(Image(cape))
            await msg.finish(chain)
        else:
            await msg.finish([Plain(f"{name} ({uuid})"), Url(namemc)])
    except ValueError:
        await msg.finish(I18NContext("mcplayer.message.not_found", player=arg))
