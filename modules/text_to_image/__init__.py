from core.builtins import Image, Bot
from core.component import module
from core.extra import pir

t2i = module('text_to_image', alias='t2i', developers='haoye_qwq', desc='Pillow Image Render')


@t2i.handle('<text> {文字转图片，字体为NotoSansXJB}')
async def _(send: Bot.MessageSession):
    await send.sendMessage(Image(pir(send.parsed_msg['<text>'],word_wrap=True)))
