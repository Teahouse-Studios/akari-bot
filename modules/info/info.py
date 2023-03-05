from core.builtins import Bot, Image
from core.component import on_command
from core.utils.image_table import image_table_render, ImageTable

inf = on_command('info')

@inf.handle()
async def inf_helps(msg: Bot.MessageSession):
    inf = msg.options.get('command_alias')
    if inf is None:
        inf = {}
    else:
        if len(inf) == 0:
            await msg.sendMessage('自定义命令别名列表为空。')
        else:
            table = ImageTable([[k, inf[k]] for k in inf], ['别名', '命令'])
            img = await image_table_render(table)
            if img:
                await msg.sendMessage(['自定义命令别名列表：', Image(img)])
            else:
                await msg.sendMessage(f'自定义命令别名列表：\n' + '\n'.join([f'{k} -> {inf[k]}' for k in inf]))