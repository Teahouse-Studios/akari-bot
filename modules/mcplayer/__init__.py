from core.builtins import Bot
from core.builtins import Plain, Image, Url
from core.component import module
from .mojang_api import *

mcplayer = module(
    bind_prefix='mcplayer',
    desc='{mcplayer.help.desc}',
    developers=['Dianliang233'],
)


@mcplayer.handle('<username_or_uuid> {{mcplayer.help}}')
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
        sac = await uuid_to_skin_and_cape(uuid)
        render = sac['render']
        skin = sac['skin']
        cape = sac['cape']
        namemc = 'https://namemc.com/profile/' + name
        chain = [Plain(f'{name}（{uuid}）\nNameMC：{Url(namemc)}'), Image(render), Image(skin)]
        if cape:
            chain.append(Image(cape))
    except ValueError:
        chain = [Plain(msg.locale.t('mcplayer.message.not_found', player=arg))]
    await msg.finish(chain)
