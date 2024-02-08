import os

from PIL import Image, ImageDraw, ImageFont

from core.builtins import Bot, Image as BImage, Plain
from core.component import module
from core.utils.cache import random_cache_path
from core.utils.http import get_url


assets_path = os.path.abspath('./assets/arcaea')


arc = module('arcaea', developers=['OasisAkari'], desc='{arcaea.help.desc}',
             alias=['a', 'arc'])


@arc.command('b30')
async def _(msg: Bot.MessageSession):
    await msg.send_message([Plain(msg.locale.t("arcaea.message.sb616")),
                            BImage(os.path.abspath('./assets/arcaea/noc.jpg'))])


@arc.command('download {{arcaea.help.download}}')
async def _(msg: Bot.MessageSession):
    resp = await get_url('https://webapi.lowiro.com/webapi/serve/static/bin/arcaea/apk/', 200,
                         fmt='json')
    if resp:
        await msg.finish([Plain(msg.locale.t("arcaea.message.download", version=resp["value"]["version"],
                                             url=resp['value']['url']))])
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))


@arc.command('random {{arcaea.help.random}}')
async def _(msg: Bot.MessageSession):
    resp = await get_url('https://webapi.lowiro.com/webapi/song/showcase/',
                         200, fmt='json')
    if resp:
        value = resp["value"][0]
        image = f'{assets_path}/jacket/{value["song_id"]}.jpg'
        result = [Plain(value["title"]["en"])]
        if os.path.exists(image):
            result.append(BImage(path=image))
        await msg.finish(result)
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))


@arc.command('rank free {{arcaea.help.rank.free}}',
             'rank paid {{arcaea.help.rank.paid}}')
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get('free', False):
        resp = await get_url('https://webapi.lowiro.com/webapi/song/rank/free/',
                             200, fmt='json')
    else:
        resp = await get_url('https://webapi.lowiro.com/webapi/song/rank/paid/',
                             200, fmt='json')
    if resp:
        r = []
        rank = 0
        for x in resp['value']:
            rank += 1
            r.append(f'{rank}. {x["title"]["en"]} ({x["status"]})')
        await msg.finish('\n'.join(r))
    else:
        await msg.finish(msg.locale.t("arcaea.message.get_failed"))


@arc.command('calc <score> <rating> {{arcaea.help.calc}}')
async def _(msg: Bot.MessageSession, score: int, rating: float):
    if score >= 10000000:
        ptt = rating + 2
    elif score >= 9800000:
        ptt = rating + 1 + (score - 9800000) / 200000
    else:
        ptt = rating + (score - 9500000) / 300000
    await msg.finish([Plain(round(max(0, ptt), 2))])


p = module('ptt', developers=['OasisAkari'])


@p.command('<potential> {{ptt.help}}')
async def pttimg(msg: Bot.MessageSession):
    ptt = msg.parsed_msg['<potential>']
    # ptt
    if ptt == '--':
        ptt = -1
    else:
        try:
            ptt = float(ptt)
        except ValueError:
            await msg.finish(msg.locale.t('ptt.message.invalid'))
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
        pttimg = Image.new("RGBA", (font1_width + font2_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        stroke_color = '#52495d'
        if int(ptt1) >= 13:
            stroke_color = '#81122F'
        drawptt.text((0, 0), ptt1 + '.', 'white', font=font1, stroke_width=3, stroke_fill=stroke_color)
        drawptt.text((font1_width, int(int(font1_height) - int(font2_height))), ptt2, 'white', font=font2,
                     stroke_width=3, stroke_fill=stroke_color)
    elif ptt == -1:
        ptt = '--'
        ptttext_width, ptttext_height = ptttext.size
        font1_width, font1_height = font1.getsize(ptt)
        pttimg = Image.new("RGBA", (font1_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        drawptt.text((0, 0), ptt, 'white', font=font1, stroke_width=3, stroke_fill='#52495d')
    else:
        return await msg.finish(msg.locale.t('ptt.message.invalid'))
    pttimg_width, pttimg_height = pttimg.size
    ptttext.alpha_composite(pttimg,
                            (int((ptttext_width - pttimg_width) / 2), int((ptttext_height - pttimg_height) / 2) - 11))
    ptttext = ptttext.resize(pttimgr.size)
    pttimgr.alpha_composite(ptttext, (0, 0))
    savepath = random_cache_path() + '.png'
    pttimgr.save(savepath)
    await msg.finish([BImage(path=savepath)])
