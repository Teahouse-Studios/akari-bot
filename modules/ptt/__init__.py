import os

from PIL import Image, ImageDraw, ImageFont

from core.component import on_command
from core.elements import Image as Img, MessageSession
from core.utils import cache_name

assets_path = os.path.abspath('./assets/arcaea')


def text_border(draw, x, y, text, shadowcolor, fillcolor, font):
    x = x + 3
    y = y + 3
    # thin border
    draw.text((x - 3, y), text, font=font, fill=shadowcolor)
    draw.text((x + 3, y), text, font=font, fill=shadowcolor)
    draw.text((x, y - 3), text, font=font, fill=shadowcolor)
    draw.text((x, y + 3), text, font=font, fill=shadowcolor)

    # thicker border
    draw.text((x - 3, y - 3), text, font=font, fill=shadowcolor)
    draw.text((x + 3, y - 3), text, font=font, fill=shadowcolor)
    draw.text((x - 3, y + 3), text, font=font, fill=shadowcolor)
    draw.text((x + 3, y + 3), text, font=font, fill=shadowcolor)

    # now draw the text over it
    draw.text((x, y), text, font=font, fill=fillcolor)


p = on_command('ptt',
               developers=['OasisAkari'])


@p.handle('<potential> {生成一张Arcaea Potential图片}')
async def pttimg(msg: MessageSession):
    ptt = msg.parsed_msg['<potential>']
    # ptt
    if ptt == '--':
        ptt = -1
    else:
        ptt = float(ptt)
    if ptt >= 12.50:
        pttimg = 6
    elif ptt >= 12.00:
        pttimg = 5
    elif ptt >= 11.00:
        pttimg = 4
    elif ptt >= 10.00:
        pttimg = 3
    elif ptt >= 7.00:
        pttimg = 2
    elif ptt >= 3.50:
        pttimg = 1
    elif ptt >= 0:
        pttimg = 0
    else:
        pttimg = 'off'
    pttimgr = Image.open(f'{assets_path}/ptt/rating_{str(pttimg)}.png')
    ptttext = Image.new("RGBA", (119, 119))
    font1 = ImageFont.truetype(os.path.abspath(f'{assets_path}/Fonts/Exo-SemiBold.ttf'), 49)
    font2 = ImageFont.truetype(os.path.abspath(f'{assets_path}/Fonts/Exo-SemiBold.ttf'), 33)
    if ptt >= 0 and ptt <= 99.99:
        rawptt = str(ptt).split('.')
        if len(rawptt) < 2:
            ptt1 = rawptt[0]
            ptt2 = '00'
        else:
            ptt1 = rawptt[0]
            ptt2 = rawptt[1][:2]
            if len(ptt2) < 2:
                ptt2 += '0'
        ptttext_width, ptttext_height = ptttext.size
        font1_width, font1_height = font1.getsize(ptt1 + '.')
        font2_width, font2_height = font2.getsize(ptt2)
        print(font1_width, font1_height)
        print(font2_width, font2_height)
        pttimg = Image.new("RGBA", (font1_width + font2_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        text_border(drawptt, 0, 0,
                    ptt1 + '.',
                    '#52495d', 'white', font=font1)
        print(int(int(font1_height) - int(font2_height)))
        text_border(drawptt, font1_width, 16, ptt2,
                    '#52495d', 'white', font=font2)
    elif ptt == -1:
        ptt = '--'
        ptttext_width, ptttext_height = ptttext.size
        font1_width, font1_height = font1.getsize(ptt)
        pttimg = Image.new("RGBA", (font1_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        text_border(drawptt, 0, 0,
                    ptt,
                    '#52495d', 'white', font=font1)
    else:
        return await msg.sendMessage('发生错误：potential 必须为 ≥0.00 且 ≤99.99 的数字。')
    pttimg_width, pttimg_height = pttimg.size
    ptttext.alpha_composite(pttimg,
                            (int((ptttext_width - pttimg_width) / 2), int((ptttext_height - pttimg_height) / 2) - 11))
    pttimgr.alpha_composite(ptttext, (0, 0))
    savepath = cache_name() + '.png'
    pttimgr.save(savepath)
    await msg.sendMessage([Img(path=savepath)])
