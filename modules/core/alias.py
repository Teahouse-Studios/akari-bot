from core.builtins import Bot, Image
from core.component import on_command
from core.utils.image_table import image_table_render, ImageTable

ali = on_command('alias', required_admin=True, base=True)


@ali.handle('add <alias> <command> {添加自定义命令别名}', 'remove <alias> {移除自定义命令别名}',
            'reset {重置自定义命令别名}',
            'list {列出自定义命令别名列表}')
async def set_alias(msg: Bot.MessageSession):
    alias = msg.options.get('command_alias')
    arg1 = msg.parsed_msg.get('<alias>', False)
    arg2 = msg.parsed_msg.get('<command>', False)
    if alias is None:
        alias = {}
    if 'add' in msg.parsed_msg:
        if arg1 not in alias:
            has_prefix = False
            for prefixes in msg.prefixes:
                if arg2.startswith(prefixes):
                    has_prefix = True
                    break
            if not has_prefix:
                await msg.sendMessage(f'添加的别名对应的命令必须以命令前缀开头，请检查。')
                return
            alias[arg1] = arg2
            msg.data.edit_option('command_alias', alias)
            await msg.sendMessage(f'已添加自定义命令别名：{arg1} -> {arg2}')
        else:
            await msg.sendMessage(f'[{arg1}]别名已存在于自定义别名列表。')
    elif 'remove' in msg.parsed_msg:
        if arg1 in alias:
            del alias[arg1]
            msg.data.edit_option('command_alias', alias)
            await msg.sendMessage(f'已移除自定义命令别名：{arg1}')
        else:
            await msg.sendMessage(f'[{arg1}]别名不存在于自定义别名列表。')
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_alias', {})
        await msg.sendMessage('已重置自定义命令别名列表。')
    elif 'list' in msg.parsed_msg:
        if len(alias) == 0:
            await msg.sendMessage('自定义命令别名列表为空。')
        else:
            table = ImageTable([[k, alias[k]] for k in alias], ['别名', '命令'])
            img = await image_table_render(table)
            if img:
                await msg.sendMessage(['自定义命令别名列表：', Image(img)])
            else:
                await msg.sendMessage(f'自定义命令别名列表：\n' + '\n'.join([f'{k} -> {alias[k]}' for k in alias]))

