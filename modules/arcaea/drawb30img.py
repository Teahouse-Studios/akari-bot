import asyncio
import os
import random
import traceback
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .utils import autofix_character

assets_path = os.path.abspath('./assets/arcaea')


def makeShadow(image, iterations, border, offset, backgroundColour, shadowColour):
    fullWidth = image.size[0] + abs(offset[0]) + 2 * border
    fullHeight = image.size[1] + abs(offset[1]) + 2 * border
    shadow = Image.new(image.mode, (fullWidth, fullHeight), backgroundColour)
    shadowLeft = border + max(offset[0], 0)
    shadowTop = border + max(offset[1], 0)
    shadow.paste(shadowColour,
                 (shadowLeft, shadowTop,
                  shadowLeft + image.size[0],
                  shadowTop + image.size[1]))
    for i in range(iterations):
        shadow = shadow.filter(ImageFilter.BLUR)
    imgLeft = border - min(offset[0], 0)
    imgTop = border - min(offset[1], 0)
    shadow.paste(image, (imgLeft, imgTop))
    return shadow


def drawb30(Username, b30, r10, ptt, character, path='', official=False):
    # background
    if not official:
        bgimgpath = f'{assets_path}/world/'
    else:
        bgimgpath = f'{assets_path}/world_official/'
    bglist = os.listdir(bgimgpath)
    bgr = random.randint(0, len(bglist) - 1)
    bg = Image.open(bgimgpath + f'/{bglist[bgr]}').convert("RGBA")
    bg = bg.resize((bg.size[0] * 2, bg.size[1] * 2))
    offset = random.randint(0, 1024)
    if not official:
        if bg.width < 2489:
            bgmut = 2489 / bg.width
            bg = bg.resize((int(bg.width * bgmut), int(bg.height * bgmut)))
        b30img = bg.crop((0, offset, 2489, 1400 + offset))
    else:
        if bg.width < 1975:
            bgmut = 1975 / bg.width
            bg = bg.resize((int(bg.width * bgmut), int(bg.height * bgmut)))
        b30img = bg.crop((0, offset, 1975, 1610 + offset))

    if not official:
        # triangle
        tg = Image.open(f'{assets_path}/triangle.png')
        b30img.alpha_composite(tg.convert("RGBA"), (1580, 550))
        # character
        character_img_path = f'{assets_path}/char/{str(character)}.png'
        if os.path.exists(character_img_path):
            character = Image.open(character_img_path)
            b30img.alpha_composite(character.convert("RGBA"), (1660, 350))
        else:
            asyncio.create_task(autofix_character(str(character)))

    # usercard overlay
    cardoverlay = Image.open(f'{assets_path}/card_overlay.png')
    if not official:
        b30img.alpha_composite(cardoverlay.convert("RGBA"), (1750, 1227))
    else:
        b30img.alpha_composite(makeShadow(cardoverlay.convert("RGBA"), 2, 3, [3, 3], 'rgba(0,0,0,0)', '#000000'),
                               (b30img.width - 500, 68))
    # ptt
    pttimg = 'off'
    if ptt is not None and isinstance(ptt, (int, float)):
        if ptt >= 13.00:
            pttimg = 7
        elif ptt >= 12.50:
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
    pttimg = Image.open(f'{assets_path}/ptt/rating_{str(pttimg)}.png')
    pttimg = pttimg.resize((75, 75))
    if not official:
        b30img.alpha_composite(pttimg.convert("RGBA"), (1775, 1226))
    else:
        b30img.alpha_composite(pttimg.convert("RGBA"), (b30img.width - 450, 67))
    ptttext = Image.new("RGBA", (200, 200))
    ptttext_width, ptttext_height = ptttext.size
    font1 = ImageFont.truetype(f'{assets_path}/Fonts/Exo-SemiBold.ttf', 30)
    font2 = ImageFont.truetype(f'{assets_path}/Fonts/Exo-SemiBold.ttf', 21)
    if ptt is not None and isinstance(ptt, (int, float)):
        rawptt = str(ptt).split('.')
        ptt1 = rawptt[0]
        ptt2 = rawptt[1]
        if len(ptt2) < 2:
            ptt2 += '0'
        font1_width, font1_height = font1.getsize(ptt1 + '.')
        font2_width, font2_height = font2.getsize(ptt2)
        pttimg = Image.new("RGBA", (font1_width + font2_width + 4, font1_height + 4))
        drawptt = ImageDraw.Draw(pttimg)
        stroke_color = '#52495d'
        if int(ptt1) >= 13:
            stroke_color = '#81122F'
        drawptt.text((0, 0), ptt1 + '.', 'white', font=font1, stroke_width=2, stroke_fill=stroke_color)
        drawptt.text((font1_width, 9), ptt2, 'white', font=font2, stroke_width=2, stroke_fill=stroke_color)
    else:
        font1_width, font1_height = font1.getsize('--')
        pttimg = Image.new("RGBA", (font1_width, font1_height))
        drawptt = ImageDraw.Draw(pttimg)
        drawptt.text((0, 0), '--', 'white', font=font1, stroke_width=2, stroke_fill='#52495d')

    pttimg_width, pttimg_height = pttimg.size
    ptttext.alpha_composite(pttimg,
                            (int((ptttext_width - pttimg_width) / 2), int((ptttext_height - pttimg_height) / 2)))
    if not official:
        b30img.alpha_composite(ptttext, (1713, 1157))
    else:
        b30img.alpha_composite(ptttext, (b30img.width - 512, 0))
    # username
    userfont = ImageFont.truetype(f'{assets_path}/Fonts/GeosansLight.ttf', 45)
    textdraw = ImageDraw.Draw(b30img)
    if not official:
        textdraw.text((1871, 1225), Username, '#3a4853', font=userfont, stroke_width=2, stroke_fill='white')
    else:
        textdraw.text((b30img.width - 365, 70), Username, '#3a4853', font=userfont, stroke_width=2, stroke_fill='white')
    # b30
    b30font = ImageFont.truetype(f'{assets_path}/Fonts/Exo-Medium.ttf', 17)
    br30 = f'B30: {str(b30)}  R10: {str(r10)}'
    if not official:
        textdraw.text((1876, 1270), br30, '#3a4853', font=b30font, stroke_width=2, stroke_fill='white')
    else:
        textdraw.text((b30img.width - 360, 113), br30, '#3a4853', font=b30font, stroke_width=2, stroke_fill='white')
    # disclaimer
    disclaimer_font = ImageFont.truetype(f'{assets_path}/Fonts/Exo-Medium.ttf', 25)
    if official:
        textdraw.text((5, 5), f'Based on ArcaeaLimitedAPI by Lowiro | Generated by Teahouse Studios "Akaribot"'
                              f'\nThis service utilizes API functionality provided by and with permission from lowiro. It is not affiliated with or endorsed by lowiro.',
                      '#3a4853', font=b30font, stroke_fill='white', stroke_width=2)
    else:
        textdraw.text((b30img.width - 490, 5), f'Based on BotArcAPI | Generated by Teahouse Studios "Akaribot"',
                      '#3a4853', font=b30font, stroke_fill='white', stroke_width=2)
    # b30card
    i = 0
    fname = 1
    t = 0
    s = 0
    while True:
        try:
            cardimg = Image.open(os.path.abspath(f'{path}/{str(fname)}.png'))
            w = (15 if not official else 115) + 345 * i
            h = (15 if not official else 185)
            if s == 5:
                s = 0
                t += 1
            h = h + 220 * t
            w = w - 345 * 5 * t
            i += 1
            cardimg = makeShadow(cardimg, 4, 9, [0, 3], 'rgba(0,0,0,0)', '#000000')
            b30img.alpha_composite(cardimg, (w, h))
            fname += 1
            s += 1
        except FileNotFoundError:
            break
        except Exception:
            traceback.print_exc()
            break
    if __name__ == '__main__':
        b30img.show()
    else:
        savefilename = os.path.abspath(f'./cache/{str(uuid.uuid4())}.jpg')
        b30img.convert("RGB").save(savefilename)
        return savefilename


if __name__ == '__main__':
    drawb30('OasisAkdfsfari', '10.250', '10.250', 12.31, '0', official=False)
