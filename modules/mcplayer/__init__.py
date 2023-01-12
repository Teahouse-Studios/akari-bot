from core.builtins.message import MessageSession
from core.component import on_command
from core.elements import Plain, Image, Url
from .mojang_api import *


mcplayer = on_command(
    bind_prefix='mcplayer',
    alias=['mcp'],
    desc='从 Mojang API 获取 Minecraft Java 版玩家信息',
    developers=['Dianliang233'],
)


@mcplayer.handle('<username_or_uuid> {通过玩家名或玩家 UUID 获取玩家信息。}')
async def main(msg: MessageSession):
    arg = msg.parsed_msg['<username_or_uuid>']
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
        chain = [Plain(f'未找到 {arg} 的信息。')]
    await msg.finish(chain)
