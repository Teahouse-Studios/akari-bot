import os
import re
import time

from PIL import Image, ImageDraw, ImageFont

assets_path = os.path.abspath('./assets/arcaea')


def dsimg(img, rank, name, difficulty, score, ptt, realptt, pure, far, lost, playtime, path=''):
    # score rating
    if score >= 9900000:
        scoretype = 'EX+'
    elif score >= 9800000:
        scoretype = 'EX'
    elif score >= 9500000:
        scoretype = 'AA'
    elif score >= 9200000:
        scoretype = 'A'
    elif score >= 8900000:
        scoretype = 'B'
    elif score >= 8600000:
        scoretype = 'C'
    else:
        scoretype = 'D'
    # song ptt
    realptt = realptt / 10
    if ptt > realptt or ptt < realptt:
        ptt = f'{realptt} > {round(ptt, 4)}'
    else:
        ptt = str(realptt)
    # playtime
    nowtime = time.time()
    playtime = playtime // 1000 - nowtime
    playtime = - playtime
    t = playtime / 60 / 60 / 24
    dw = 'd'
    if t < 1:
        t = playtime / 60 / 60
        dw = 'h'
        if t < 1:
            t = playtime / 60
            dw = 'm'
        if t < 1:
            t = playtime
            dw = 's'
    playtime = str(int(t)) + dw
    # drawimg
    songimg = Image.open(img).convert("RGBA")
    font = ImageFont.truetype(f'{assets_path}/Fonts/Kazesawa-Regular.ttf', 40)
    font2 = ImageFont.truetype(f'{assets_path}/Fonts/Exo-SemiBold.ttf', 27)
    difficultyimg = Image.open(f'{assets_path}/{difficulty}.png')
    songimg.alpha_composite(difficultyimg.convert("RGBA"), (278, 0))
    drawtext = ImageDraw.Draw(songimg)
    drawtext.text((20, 115), '#' + str(rank), '#ffffff', font=font)
    name_length = len(name)
    if name_length > 14:
        name = name[0:14] + '...'
    drawtext.text((20, 1), name, '#ffffff', font=font)
    score = re.sub(',', "'", format(score, ','))
    score = score.split("'")
    if int(score[0]) < 10:
        score = "'".join(score)
        score = '0' + score
    else:
        score = "'".join(score)
    drawtext.text((20, 50), f'{score}  [{scoretype}]', '#ffffff', font=font2)
    drawtext.text((20, 80), f'Potential: {ptt}', '#ffffff', font=font2)
    drawtext.text((120, 115), f'P {str(pure)}', '#ffffff', font=font2)
    drawtext.text((120, 145), f'F {str(far)} L {str(lost)}', '#ffffff', font=font2)
    songimg_width = songimg.size[0]
    playtime_width = font2.getsize(playtime)[0]
    drawtext.text((songimg_width - playtime_width - 13, 160), playtime, '#ffffff', font=font2)
    if __name__ == '__main__':
        songimg.show()
    else:
        songimg.save(f'{path}/{str(rank)}.png')


if __name__ == '__main__':
    dsimg(os.path.abspath(f'./assets/songimg/mahoroba.jpg'), '20', 'MAHOROBA', '2', 10000000, 12, 13, '999', '0', '0',
          1601545604789)
