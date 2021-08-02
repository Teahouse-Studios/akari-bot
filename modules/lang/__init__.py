import traceback

from core.elements import MessageSession
from core.loader.decorator import command
from core.i18n import BotI18n

@command('lang', ('i18n', 'language', 'languages'), (
    '~lang current {获取当前语言}',
    '~lang set <target> {设置群组使用语言}',
    '~lang get <string> {获取指定字符串}'),
    need_admin=True, is_base_function=True
)
async def lang(msg: MessageSession):
    i18n = BotI18n(msg)
    if msg.parsed_msg['set']:
        await i18n.set_language(msg.parsed_msg['<target>'])
        await msg.sendMessage('设置成功。')
        
    elif msg.parsed_msg['get']:
        await msg.sendMessage(await i18n.get_string(msg.parsed_msg['<string>']))
    elif msg.parsed_msg['current']:
        await msg.sendMessage(i18n.uselang)
