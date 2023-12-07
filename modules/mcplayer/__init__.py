from core.builtins import Bot, Plain, Image, Url
from core.component import module
from .mojang_api import *

mcplayer = module(
    bind_prefix='mcplayer',
    desc='{mcplayer.help.desc}',
    developers=['Dianliang233'],
)


@mcplayer.command('<username_or_uuid> {{mcplayer.help}}')
async def main(msg: Bot.MessageSession, username_or_uuid: str):
    arg = username_or_uuid
    try:
        if len(arg) == 32:
            name = await uuid_to_name(arg)
            uuid = arg
        elif len(arg) == 36 and arg.count('-') == 4:
            uuid = arg.replace('-', '')
            name = await uuid_to_name(arg)
        else:
            name = arg
            uuid = await name_to_uuid(arg)
        namemc = 'https://namemc.com/profile/' + name
        sac = await uuid_to_skin_and_cape(uuid)
        if sac:
            render = sac['render']
            skin = sac['skin']
            cape = sac['cape']
            chain = [Plain(f'{name}（{uuid}）\nNameMC：{Url(namemc)}'), Image(render), Image(skin)]
            if cape:
                chain.append(Image(cape))
            await msg.finish(chain)
        else:
            await msg.finish(f'{name}（{uuid}）\nNameMC：{Url(namemc)}')
    except ValueError:
        await msg.finish(msg.locale.t('mcplayer.message.not_found', player=arg))
