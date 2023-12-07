from core.builtins import Bot, Image, Plain
from core.component import module
from .screenshot import get_pic

dict = module('dictionary', alias="dict",
                     desc='{dictionary.help.desc}', developers=['Dianliang233'], support_languages=['en_us'])


@dict.command(help_doc='<term> {{dictionary.help}}')
async def _(msg: Bot.MessageSession, term: str):
    pic_collins = await get_pic(
        'https://www.collinsdictionary.com/dictionary/english/' + str(term).replace(' ',
                                                                                    '-').lower(),
        'collins')
    # pic_yd = await get_pic('https://www.youdao.com/result?word=' + msg.parsed_msg['<term>'] + '&lang=en', 'yd')
    # if pic_collins or pic_yd:
    if pic_collins:
        # await msg.finish([Image(pic_collins), Image(pic_yd),
        await msg.finish([Image(pic_collins), Plain(
            f'https://www.collinsdictionary.com/dictionary/english/{term}')])
# 有道：https://www.youdao.com/result?lang=en&word={msg.parsed_msg["<term>"]}'''])
