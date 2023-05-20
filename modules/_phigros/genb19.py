import asyncio
import os
import random
import traceback
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

assets_path = os.path.abspath('./assets/phigros')


def drawb19(username, b19data):
    b19img = Image.new("RGBA", (1590, 1340), '#1e2129')
    # b30card
    i = 0
    fname = 1
    t = 0
    s = 0
    for song in b19data:
        try:
            if song.id == '':
                cardimg = Image.new('RGBA', (384, 240), 'black')
            else:
                imgpath = os.path.abspath(f'{assets_path}/illustration/{song.id.split(".")[0]}')
                if not os.path.exists(imgpath):
                    imgpath = os.path.abspath(f'{assets_path}/illustration/{song.id}.png')
                if not os.path.exists(imgpath):
                    cardimg = Image.new('RGBA', (384, 240), 'black')
                else:
                    cardimg = Image.open(imgpath)
                    if cardimg.mode != 'RGBA':
                        cardimg = cardimg.convert('RGBA')
                    downlight = ImageEnhance.Brightness(cardimg)
                    img_size = downlight.image.size
                    resize_multiplier = 384 / img_size[0]
                    img_h = int(img_size[1] * resize_multiplier)
                    if img_h < 240:
                        resize_multiplier = 240 / img_size[1]
                        resize_img_w = int(img_size[0] * resize_multiplier)
                        resize_img_h = int(img_size[1] * resize_multiplier)
                        crop_start_x = int((resize_img_w - 384) / 2)
                        crop_start_y = int((resize_img_h - 240) / 2)
                        cardimg = downlight.enhance(0.5).resize((resize_img_w,
                                                                 resize_img_h),
                                                                ).crop((crop_start_x, crop_start_y,
                                                                        384 + crop_start_x, 240 + crop_start_y))
                    elif img_h > 240:
                        crop_start_y = int((img_h - 240) / 2)
                        cardimg = downlight.enhance(0.5).resize((384, img_h)) \
                            .crop((0, crop_start_y, 384, 240 + crop_start_y))
                    else:
                        cardimg = downlight.enhance(0.5).resize((384, img_h))
            w = 15 + 384 * i
            h = 100
            if s == 4:
                s = 0
                t += 1
            h = h + 240 * t
            w = w - 384 * 4 * t
            i += 1
            triangle_img = Image.new('RGBA', (100, 100), 'rgba(0,0,0,0)')
            draw = ImageDraw.Draw(triangle_img)
            draw.polygon([(0, 0), (0, 100), (100, 0)], fill=['#11b231', '#0273b7', '#cd1314', '#383838'][song.level])
            text_img = Image.new('RGBA', (70, 70), 'rgba(0,0,0,0)')
            font = ImageFont.truetype(os.path.abspath('./assets/Noto Sans CJK DemiLight.otf'), 20)
            font2 = ImageFont.truetype(os.path.abspath('./assets/Noto Sans CJK DemiLight.otf'), 15)
            font3 = ImageFont.truetype(os.path.abspath('./assets/Noto Sans CJK DemiLight.otf'), 25)
            text_draw = ImageDraw.Draw(text_img)
            text1 = ['EZ', 'HD', 'IN', 'AT'][song.level]
            text2 = str(round(song.difficulty, 1))
            text_size1 = font.getbbox(text1)
            text_size2 = font2.getbbox(text2)
            text_draw.text(((text_img.width - text_size1[2]) / 2, (text_img.height - text_size1[3]) / 2), text1,
                           font=font,
                           fill='#FFFFFF')
            text_draw.text(((text_img.width - text_size2[2]) / 2, (text_img.height - text_size2[3]) / 2 + 20), text2,
                           font=font2, fill='#FFFFFF')

            triangle_img.alpha_composite(text_img.rotate(45, expand=True), (-25, -25))
            cardimg.alpha_composite(triangle_img.resize((75, 75)), (0, 0))
            draw_card = ImageDraw.Draw(cardimg)
            draw_card.text((20, 155), song.id, '#ffffff', font=font3)
            draw_card.text((20, 180), f'Score: {song.s} Acc: {song.a}\nRks: {song.rks}', '#ffffff', font=font)

            b19img.alpha_composite(cardimg, (w, h))
            fname += 1
            s += 1
        except Exception:
            traceback.print_exc()
            break
    if __name__ == '__main__':
        b19img.show()
    else:
        savefilename = os.path.abspath(f'./cache/{str(uuid.uuid4())}.jpg')
        b19img.convert("RGB").save(savefilename)
        return savefilename


if __name__ == '__main__':
    from thrift.transport import TSocket
    from thrift.transport import TTransport
    from thrift.protocol import TBinaryProtocol

    from phigrosLibrary import Phigros

    transport = TTransport.TBufferedTransport(TSocket.TSocket())
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = Phigros.Client(protocol)
    transport.open()
    saveurl = client.getSaveUrl('kqt1ptgjwniiab6z7k8xk9hm4')
    result = client.best19(saveurl.saveUrl)
    drawb19('', result)
    transport.close()
