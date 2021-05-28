import os
import random
import traceback
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter


def text_border(draw, x, y, text, shadowcolor, fillcolor, font):
    x = x + 2
    y = y + 2
    # thin border
    draw.text((x - 2, y), text, font=font, fill=shadowcolor)
    draw.text((x + 2, y), text, font=font, fill=shadowcolor)
    draw.text((x, y - 2), text, font=font, fill=shadowcolor)
    draw.text((x, y + 2), text, font=font, fill=shadowcolor)

    # thicker border
    draw.text((x - 2, y - 2), text, font=font, fill=shadowcolor)
    draw.text((x + 2, y - 2), text, font=font, fill=shadowcolor)
    draw.text((x - 2, y + 2), text, font=font, fill=shadowcolor)
    draw.text((x + 2, y + 2), text, font=font, fill=shadowcolor)

    # now draw the text over it
    draw.text((x, y), text, font=font, fill=fillcolor)


def makeShadow(image, iterations, border, offset, backgroundColour, shadowColour):
    fullWidth = image.size[0] + abs(offset[0]) + 2 * border
    fullHeight = image.size[1] + abs(offset[1]) + 2 * border
    shadow = Image.new(image.mode, (fullWidth, fullHeight), backgroundColour)
    shadowLeft = border + max(offset[0], 0)
    shadowTop = border + max(offset[1], 0)
    shadow.paste(shadowColour,
                 [shadowLeft, shadowTop,
                  shadowLeft + image.size[0],
                  shadowTop + image.size[1]])
    for i in range(iterations):
        shadow = shadow.filter(ImageFilter.BLUR)
    imgLeft = border - min(offset[0], 0)
    imgTop = border - min(offset[1], 0)
    shadow.paste(image, (imgLeft, imgTop))
    return shadow


def drawb30(Username, b30, r10, ptt, character, path=''):
    # backgroud
    bgimgpath = os.path.abspath('./assets/arcaea/world/')
    bglist = os.listdir(bgimgpath)
    bgr = random.randint(0, len(bglist))
    bg = Image.open(bgimgpath + f'/{bglist[bgr]}')
    bg = bg.resize((bg.size[0] * 2, bg.size[1] * 2))
    offset = random.randint(0, 1024)
    b30img = bg.crop((0, offset, 2489, 1400 + offset))
    # triangle
    tg = Image.open(os.path.abspath('./assets/arcaea/triangle.png'))
    b30img.alpha_composite(tg.convert("RGBA"), (1580, 550))
    # character
    try:
        character = Image.open(os.path.abspath(f'./assets/arcaea/char/{str(character)}.png'))
        b30img.alpha_composite(character.convert("RGBA"), (1660, 350))
    except Exception:
        pass
    # usercard overlay
    cardoverlay = Image.open(os.path.abspath('./assets/arcaea/card_overlay.png'))
    b30img.alpha_composite(cardoverlay.convert("RGBA"), (1750, 1227))
    # ptt
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
    pttimg = Image.open(os.path.abspath(f'./assets/arcaea/ptt/rating_{str(pttimg)}.png'))
    pttimg = pttimg.resize((75, 75))
    b30img.alpha_composite(pttimg.convert("RGBA"), (1775, 1226))
    ptttext = Image.new("RGBA", (200, 200))
    font1 = ImageFont.truetype(os.path.abspath('./assets/arcaea/Fonts/Exo-SemiBold.ttf'), 30)
    font2 = ImageFont.truetype(os.path.abspath('./assets/arcaea/Fonts/Exo-SemiBold.ttf'), 21)
    rawptt = str(ptt).split('.')
    ptt1 = rawptt[0]
    ptt2 = rawptt[1]
    if len(ptt2) < 2:
        ptt2 += '0'
    ptttext_width, ptttext_height = ptttext.size
    font1_width, font1_height = font1.getsize(ptt1 + '.')
    font2_width, font2_height = font2.getsize(ptt2)
    print(font1_width, font1_height)
    print(font2_width, font2_height)
    pttimg = Image.new("RGBA", (font1_width + font2_width + 4, font1_height + 4))
    drawptt = ImageDraw.Draw(pttimg)
    text_border(drawptt, 0, 0,
                ptt1 + '.',
                '#52495d', 'white', font=font1)
    print(int(int(font1_height) - int(font2_height)))
    text_border(drawptt, font1_width, 9, ptt2,
                '#52495d', 'white', font=font2)
    pttimg_width, pttimg_height = pttimg.size
    ptttext.alpha_composite(pttimg,
                            (int((ptttext_width - pttimg_width) / 2), int((ptttext_height - pttimg_height) / 2)))
    b30img.alpha_composite(ptttext, (1712, 1157))
    # username
    userfont = ImageFont.truetype(os.path.abspath('./assets/arcaea/Fonts/GeosansLight.ttf'), 45)
    textdraw = ImageDraw.Draw(b30img)
    text_border(textdraw, 1871, 1225, Username, 'white', '#3a4853', font=userfont)
    # b30
    b30font = ImageFont.truetype(os.path.abspath('./assets/arcaea/Fonts/Exo-Medium.ttf'), 17)
    text_border(textdraw, 1876, 1270, f'B30: {str(b30)}  R10: {str(r10)}', 'white', '#3a4853', font=b30font)
    # b30card
    i = 0
    fname = 1
    t = 0
    s = 0
    while True:
        try:
            cardimg = Image.open(os.path.abspath(f'{path}/{str(fname)}.png'))
            w = 15 + 345 * i
            h = 15
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
    drawb30('gggggg', '10.250', '10.250', 12.31, '0')
