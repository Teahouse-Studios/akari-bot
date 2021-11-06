import os
import shutil
import time
import traceback
import uuid
from datetime import datetime, timedelta
from os.path import abspath

import aiohttp
import ujson as json
from PIL import Image, ImageEnhance, ImageFont, ImageDraw, ImageFilter, ImageOps
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from core.utils import get_url


async def get_rating(uid, query_type):
    try:
        if query_type == 'b30':
            query_type = 'bestRecords'
        elif query_type == 'r30':
            query_type = 'recentRecords'
        Profile_url = 'http://services.cytoid.io/profile/' + uid
        Profile_json = json.loads(await get_url(Profile_url))
        if 'statusCode' in Profile_json:
            if Profile_json['statusCode'] == 404:
                return {'status': False, 'text': '发生错误：此用户不存在。'}
        ProfileId = Profile_json['user']['id']
        ProfileRating = Profile_json['rating']
        ProfileLevel = Profile_json['exp']['currentLevel']
        ProfileUid = Profile_json['user']['uid']
        nick = Profile_json['user']['name']
        if nick is None:
            nick = ProfileUid
        if 'avatar' in Profile_json['user']:
            Avatar_img = Profile_json['user']['avatar']['medium']
        else:
            Avatar_img = None
        transport = AIOHTTPTransport(url='https://services.cytoid.io/graphql')
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql(
            f"""
            query StudioAnalytics($id: ID = "{ProfileId}") {{
          profile(id: $id) {{
            id
            {query_type}(limit: 30) {{
              ...RecordFragment
            }}
          }}
        }}
        
        fragment RecordFragment on UserRecord {{
          id
          date
          chart {{
            id
            difficulty
            type
            level {{
              uid
              title
            }}
          }}
          score
          accuracy
          rating
        }}
        """)

        result = await client.execute_async(query)
        print(result)
        workdir = os.path.abspath('./cache/' + str(uuid.uuid4()))
        os.mkdir(workdir)
        bestRecords = result['profile'][query_type]
        rank = 0
        for x in bestRecords:
            thumbpath = await download_cover_thumb(x['chart']['level']['uid'])
            chart_type = x['chart']['type']
            difficulty = x['chart']['difficulty']
            chart_name = x['chart']['level']['title']
            score = str(x['score'])
            acc = x['accuracy']
            rt = x['rating']
            _date = datetime.strptime(x['date'], "%Y-%m-%dT%H:%M:%S.%fZ")
            local_time = _date + timedelta(hours=8)
            playtime = local_time.timestamp()
            nowtime = time.time()
            playtime = playtime - nowtime
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
            rank += 1
            if thumbpath:
                havecover = True
            else:
                havecover = False
            make_songcard(workdir, thumbpath, chart_type, difficulty, chart_name, score, acc, rt, playtime, rank,
                          havecover)
        # b30card
        b30img = Image.new("RGBA", (1975, 1610), '#1e2129')
        avatar_path = await download_avatar_thumb(Avatar_img, ProfileId)
        if avatar_path:
            im = Image.open(avatar_path)
            im = im.resize((110, 110))
            try:
                bigsize = (im.size[0] * 3, im.size[1] * 3)
                mask = Image.new('L', bigsize, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + bigsize, fill=255)
                mask = mask.resize(im.size, Image.ANTIALIAS)
                im.putalpha(mask)
                output = ImageOps.fit(im, mask.size, centering=(0.5, 0.5))
                output.putalpha(mask)
                output.convert('RGBA')
                b30img.alpha_composite(output, (1825, 25))
            except:
                traceback.print_exc()

        font4 = ImageFont.truetype(os.path.abspath('./assets/Nunito-Regular.ttf'), 35)
        drawtext = ImageDraw.Draw(b30img)
        get_name_width = font4.getsize(nick)[0]
        get_img_width = b30img.width
        drawtext.text((get_img_width - get_name_width - 160, 30), nick, '#ffffff', font=font4)

        font5 = ImageFont.truetype(os.path.abspath('./assets/Noto Sans CJK DemiLight.otf'), 20)
        level_text = f'等级 {ProfileLevel}'
        level_text_width = font5.getsize(level_text)[0]
        level_text_height = font5.getsize(level_text)[1]
        img_level = Image.new("RGBA", (level_text_width + 20, 40), '#050a1a')
        drawtext_level = ImageDraw.Draw(img_level)
        drawtext_level.text(((img_level.width - level_text_width) / 2, (img_level.height - level_text_height) / 2),
                            level_text, '#ffffff', font=font5)
        b30img.alpha_composite(img_level, (1825 - img_level.width - 20, 85))
        font6 = ImageFont.truetype(os.path.abspath('./assets/Nunito-Light.ttf'), 20)
        rating_text = f'Rating {str(round(float(ProfileRating), 2))}'
        rating_text_width = font6.getsize(rating_text)[0]
        rating_text_height = font6.getsize(rating_text)[1]
        img_rating = Image.new("RGBA", (rating_text_width + 20, 40), '#050a1a')
        drawtext_level = ImageDraw.Draw(img_rating)
        drawtext_level.text(((img_rating.width - rating_text_width) / 2, (img_rating.height - rating_text_height) / 2),
                            rating_text, '#ffffff', font=font6)
        b30img.alpha_composite(img_rating, (1825 - img_level.width - img_rating.width - 30, 85))

        i = 0
        fname = 1
        t = 0
        s = 0
        while True:
            try:
                cardimg = Image.open(f'{workdir}/{str(fname)}.png')
                w = 15 + 384 * i
                h = 135
                if s == 5:
                    s = 0
                    t += 1
                h = h + 240 * t
                w = w - 384 * 5 * t
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
            shutil.rmtree(workdir)
            return {'status': True, 'path': savefilename}
    except Exception as e:
        traceback.print_exc()
        return {'status': False, 'text': '发生错误：' + str(e)}


async def download_cover_thumb(uid):
    try:
        d = abspath('./assets/cytoid-cover/' + uid + '/')
        if not os.path.exists(d):
            os.makedirs(d)
        path = d + '/thumbnail.png'
        if not os.path.exists(d):
            os.mkdir(d)
        if not os.path.exists(path):
            level_url = 'http://services.cytoid.io/levels/' + uid
            get_level = json.loads(await get_url(level_url))
            cover_thumbnail = get_level['cover']['thumbnail']
            async with aiohttp.ClientSession() as session:
                async with session.get(cover_thumbnail) as resp:
                    with open(path, 'wb+') as jpg:
                        jpg.write(await resp.read())
                        return path
        else:
            return path
    except:
        traceback.print_exc()
        return False


async def download_avatar_thumb(link, id):
    try:
        d = abspath('./assets/cytoid-avatar/')
        if not os.path.exists(d):
            os.makedirs(d)
        path = d + f'/{id}.png'
        if not os.path.exists(d):
            os.mkdir(d)
        if os.path.exists(path):
            os.remove(path)
        async with aiohttp.ClientSession() as session:
            async with session.get(link, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                with open(path, 'wb+') as jpg:
                    jpg.write(await resp.read())
                    return path
    except:
        traceback.print_exc()
        return False


def make_songcard(workdir, coverpath, chart_type, difficulty, chart_name, score, acc, rt, playtime, rank,
                  havecover=True):
    if havecover:
        try:
            img = Image.open(coverpath)
        except:
            img = Image.new('RGBA', (384, 240), 'black')
    else:
        img = Image.new('RGBA', (384, 240), 'black')
    img = img.convert('RGBA')
    downlight = ImageEnhance.Brightness(img)
    d2 = downlight.enhance(0.5)
    img = d2.resize((384, 240))
    img_type = Image.open(f'./assets/cytoid/{chart_type}.png')
    img_type = img_type.convert('RGBA')
    img_type = img_type.resize((40, 40))
    img.alpha_composite(img_type, (20, 20))
    font_path = './assets/Noto Sans CJK DemiLight.otf'
    font = ImageFont.truetype(os.path.abspath(font_path), 25)
    font2 = ImageFont.truetype(os.path.abspath(font_path), 15)
    font3 = ImageFont.truetype(os.path.abspath(font_path), 20)
    drawtext = ImageDraw.Draw(img)
    drawtext.text((20, 130), score, '#ffffff', font=font3)
    drawtext.text((20, 155), chart_name, '#ffffff', font=font)
    drawtext.text((20, 185), f'Accuracy: {acc}\nRating: {rt}', font=font2)
    playtime = f'{playtime} #{rank}'
    playtime_width = font3.getsize(playtime)[0]
    songimg_width = 384
    drawtext.text((songimg_width - playtime_width - 15, 205), playtime, '#ffffff', font=font3)
    type_ = str(difficulty)
    type_text = Image.new('RGBA', (32, 32))
    draw_typetext = ImageDraw.Draw(type_text)
    draw_typetext.text(((32 - font3.getsize(type_)[0] - font.getoffset(type_)[0]) / 2, 0), type_, "#ffffff", font=font3)
    img.alpha_composite(type_text, (23, 29))
    img.save(workdir + '/' + str(rank) + '.png')


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
