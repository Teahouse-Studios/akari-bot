from core.builtins.message import MessageSession
from core.component import on_command

p = on_command('prefix', required_admin=True, base=True)


@p.handle('add <prefix> {设置自定义机器人命令前缀}', 'remove <prefix> {移除自定义机器人命令前缀}',
          'reset {重置自定义机器人命令前缀}')
async def set_prefix(msg: MessageSession):
    prefixes = msg.options.get('command_prefix')
    arg1 = msg.parsed_msg.get('<prefix>', False)
    if prefixes is None:
        prefixes = []
    if 'add' in msg.parsed_msg:
        if arg1:
            if arg1 not in prefixes:
                prefixes.append(arg1)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.sendMessage(f'已添加自定义命令前缀：{arg1}\n帮助文档将默认使用该前缀进行展示。')
            else:
                await msg.sendMessage(f'此命令前缀已存在于自定义前缀列表。')
    elif 'remove' in msg.parsed_msg:
        if arg1:
            if arg1 in prefixes:
                prefixes.remove(arg1)
                msg.data.edit_option('command_prefix', prefixes)
                await msg.sendMessage(f'已移除自定义命令前缀：{arg1}')
            else:
                await msg.sendMessage(f'此命令前缀不存在于自定义前缀列表。')
    elif 'reset' in msg.parsed_msg:
        msg.data.edit_option('command_prefix', [])
        await msg.sendMessage('已重置自定义命令前缀列表。')
