import asyncio
import os
import time
from datetime import datetime

import orjson as json
from PIL import Image, ImageEnhance, ImageFont, ImageDraw, ImageOps
from gql import Client, gql
from gql.transport.httpx import HTTPXAsyncTransport

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext, Plain
from core.config import Config
from core.constants.path import (
    assets_path,
    cache_path,
    noto_sans_demilight_path,
)
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.html2text import html2text
from core.utils.http import get_url, download
from core.utils.image import get_fontsize
from core.utils.message import parse_time_string

ctd_assets_path = os.path.join(assets_path, "modules", "cytoid")
nunito_light_path = os.path.join(ctd_assets_path, "Nunito Light.ttf")
nunito_regular_path = os.path.join(ctd_assets_path, "Nunito Regular.ttf")


def truncate_text(arg_str: str, arg_len: int) -> str:
    count = 0
    list_str = []
    for str_ in arg_str:
        inside_code = ord(str_)
        if inside_code == 0x0020:
            count += 1
        elif inside_code < 0x7F:
            count += 1
        else:
            count += 2
        if count > arg_len:
            return "".join(list_str) + "..."
        list_str.append(str_)
    return "".join(list_str)


async def get_rating(msg: Bot.MessageSession, uid, query_type):
    try:
        if query_type == "b30":
            query_type = "bestRecords"
        elif query_type == "r10":
            query_type = "recentRecords"
        profile_url = f"http://services.cytoid.io/profile/{uid}"
        profile_json = json.loads(await get_url(profile_url, 200))
        if "statusCode" in profile_json:
            if profile_json["statusCode"] == 404:
                return {
                    "status": False,
                    "text": I18NContext("cytoid.message.user_not_found"),
                }
        profile_id = profile_json["user"]["id"]
        profile_rating = profile_json["rating"]
        profile_level = profile_json["exp"]["currentLevel"]
        profile_uid = profile_json["user"]["uid"]
        nick = profile_json["user"]["name"]
        if not nick:
            nick = profile_uid
        if "avatar" in profile_json["user"]:
            avatar_img = profile_json["user"]["avatar"]["medium"]
        else:
            avatar_img = None
        transport = HTTPXAsyncTransport(url="https://services.cytoid.io/graphql")
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql(
            f"""
            query StudioAnalytics($id: ID = "{profile_id}") {{
          profile(id: $id) {{
            id
            {query_type}(limit: {30 if query_type == "bestRecords" else 10}) {{
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
          details {{
            maxCombo
            perfect
            great
            good
            bad
            miss
          }}
        }}
        """
        )

        result = await client.execute_async(query)
        best_records = result["profile"][query_type]
        if query_type == "recentRecords":
            nowtime = time.time()
            best_records = [
                x for x in best_records
                if (nowtime - datetime.strptime(x["date"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()) <= 60 * 24 * 60 * 60
            ]
        rank = 0
        resources = []
        songcards = []

        async def mkresources(msg: Bot.MessageSession, x, rank):
            thumbpath = await download_cover_thumb(x["chart"]["level"]["uid"])
            chart_type = x["chart"]["type"]
            difficulty = x["chart"]["difficulty"]
            chart_name = x["chart"]["level"]["title"]
            score = str(x["score"])
            acc = x["accuracy"]
            rt = x["rating"]
            details = x["details"]
            _date = datetime.strptime(x["date"], "%Y-%m-%dT%H:%M:%S.%fZ")
            local_time = _date + parse_time_string(
                msg.session_info.target_info.target_data.get("timezone_offset", Config("timezone_offset", "+8"))
            )
            playtime = local_time.timestamp()
            nowtime = time.time()
            playtime = playtime - nowtime
            playtime = -playtime
            t = playtime / 60 / 60 / 24
            dw = "d"
            if t < 1:
                t = playtime / 60 / 60
                dw = "h"
                if t < 1:
                    t = playtime / 60
                    dw = "m"
                if t < 1:
                    t = playtime
                    dw = "s"
            playtime = str(int(t)) + dw
            havecover = bool(thumbpath)
            songcards.append(
                make_songcard(
                    query_type,
                    thumbpath,
                    chart_type,
                    difficulty,
                    chart_name,
                    score,
                    acc,
                    rt,
                    playtime,
                    rank,
                    details,
                    havecover,
                )
            )

        for x in best_records:
            rank += 1
            resources.append(mkresources(msg, x, rank))

        await asyncio.gather(*resources)
        cards_ = await asyncio.gather(*songcards)
        cards_d = {}
        for x in cards_:
            for k in x:
                cards_d[k] = x[k]
        sorted_cards = sorted(cards_d.items(), key=lambda x: x[0])

        if best_records:
            avg_rating = sum([x["rating"] for x in best_records]) / len(best_records)
        else:
            avg_rating = 0.0
        # b30card
        img_height = 1600 if query_type == "bestRecords" else 640
        b30img = Image.new("RGBA", (1955, img_height), "#1e2129")
        avatar_path = await download_avatar_thumb(avatar_img, profile_id)
        if avatar_path:
            im = Image.open(avatar_path)
            im = im.resize((110, 110))
            try:
                bigsize = (im.size[0] * 3, im.size[1] * 3)
                mask = Image.new("L", bigsize, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + bigsize, fill=255)
                mask = mask.resize(im.size, Image.Resampling.LANCZOS)
                im.putalpha(mask)
                output = ImageOps.fit(im, mask.size, centering=(0.5, 0.5))
                output.putalpha(mask)
                output.convert("RGBA")
                b30img.alpha_composite(output, (1825, 22))
            except Exception:
                Logger.exception()

        font4 = ImageFont.truetype(nunito_regular_path, 35)
        drawtext = ImageDraw.Draw(b30img)
        get_name_width = get_fontsize(font4, nick)[0]
        get_img_width = b30img.width
        drawtext.text(
            (get_img_width - get_name_width - 150, 30), nick, "#ffffff", font=font4
        )

        font5 = ImageFont.truetype(nunito_light_path, 20)
        level_text = f"Level {profile_level}"
        level_text_size = get_fontsize(font5, level_text)
        level_text_width = level_text_size[0]
        level_text_height = level_text_size[1]
        img_level = Image.new("RGBA", (level_text_width + 20, 40), "#050a1a")
        drawtext_level = ImageDraw.Draw(img_level)
        drawtext_level.text(
            (
                (img_level.width - level_text_width) // 2.2,
                (img_level.height - level_text_height) // 2.6,
            ),
            level_text,
            "#ffffff",
            font=font5,
        )
        b30img.alpha_composite(img_level, (1825 - img_level.width - 20, 85))
        rating_text = f"Rating {float(profile_rating):.2f}"
        rating_text_size = get_fontsize(font5, rating_text)
        rating_text_width = rating_text_size[0]
        rating_text_height = rating_text_size[1]
        img_rating = Image.new("RGBA", (rating_text_width + 20, 40), "#050a1a")
        drawtext_level = ImageDraw.Draw(img_rating)
        drawtext_level.text(
            (
                (img_rating.width - rating_text_width) // 2.2,
                (img_rating.height - rating_text_height) // 2.4,
            ),
            rating_text,
            "#ffffff",
            font=font5,
        )
        b30img.alpha_composite(
            img_rating, (1825 - img_level.width - img_rating.width - 30, 85)
        )
        textdraw = ImageDraw.Draw(b30img)
        textdraw.text(
            (20, 10),
            "Generated by Teahouse Studios \"AkariBot\"",
            "white",
            font=font5,
        )
        textdraw.text(
            (20, 100),
            f"Average: {avg_rating:.2f}",
            "white",
            font=font5,
        )
        i = 0
        fname = 1
        t = 0
        s = 0
        for card in sorted_cards:
            try:
                w = 15 + 384 * i
                h = 135
                if s == 5:
                    s = 0
                    t += 1
                h = h + 240 * t
                w = w - 384 * 5 * t
                i += 1
                b30img.alpha_composite(card[1], (w, h))
                fname += 1
                s += 1
            except Exception:
                Logger.exception()
                break
        if __name__ == "__main__":
            b30img.show()
        else:
            savefilename = f"{random_cache_path()}.png"
            b30img.convert("RGB").save(savefilename)
            # shutil.rmtree(workdir)
            return {"status": True, "path": savefilename}
    except Exception as e:
        if str(e).startswith("404"):
            await msg.finish(I18NContext("cytoid.message.user_not_found"))
        Logger.exception()
        return {"status": False, "text": Plain("{I18N:message.error}" + str(e))}


async def download_cover_thumb(uid):
    try:
        filename = "thumbnail.png"
        d = os.path.join(cache_path, "cytoid-cover", uid)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        if not os.path.exists(path):
            level_url = f"http://services.cytoid.io/levels/{uid}"
            get_level = json.loads(await get_url(level_url))
            cover_thumbnail = f"{get_level["cover"]["original"]}?h=240&w=384"
            path = await download(
                cover_thumbnail, filename=filename, path=d, logging_err_resp=False
            )
        return path
    except Exception:
        Logger.exception()
        return False


async def download_avatar_thumb(link, id):
    Logger.debug(f"Downloading avatar for {id}")
    try:
        d = os.path.join(cache_path, "cytoid-avatar")
        os.makedirs(d, exist_ok=True)
        path = await download(
            link, filename=f"{id}.png", path=d, logging_err_resp=False
        )
        return path
    except Exception:
        Logger.exception()
        return False


async def make_songcard(
    query_type,
    coverpath,
    chart_type,
    difficulty,
    chart_name,
    score,
    acc,
    rt,
    playtime,
    rank,
    details,
    havecover=True,
):
    if havecover:
        try:
            img = Image.open(coverpath)
        except Exception:
            os.remove(coverpath)
            img = Image.new("RGBA", (384, 240), "black")
    else:
        img = Image.new("RGBA", (384, 240), "black")
    img = img.convert("RGBA")
    downlight = ImageEnhance.Brightness(img)
    img_size = downlight.image.size
    resize_multiplier = 384 / img_size[0]
    img_h = int(img_size[1] * resize_multiplier)
    if img_h < 240:
        resize_multiplier = 240 / img_size[1]
        resize_img_w = int(img_size[0] * resize_multiplier)
        resize_img_h = int(img_size[1] * resize_multiplier)
        crop_start_x = int((resize_img_w - 384) / 2)
        crop_start_y = int((resize_img_h - 240) / 2)
        img = (
            downlight.enhance(0.5)
            .resize(
                (resize_img_w, resize_img_h),
            )
            .crop((crop_start_x, crop_start_y, 384 + crop_start_x, 240 + crop_start_y))
        )
    elif img_h > 240:
        crop_start_y = int((img_h - 240) / 2)
        img = (
            downlight.enhance(0.5)
            .resize((384, img_h))
            .crop((0, crop_start_y, 384, 240 + crop_start_y))
        )
    else:
        img = downlight.enhance(0.5).resize((384, img_h))
    img_type = Image.open(os.path.join(ctd_assets_path, f"{chart_type}.png"))
    img_type = img_type.convert("RGBA")
    img_type = img_type.resize((40, 40))
    img.alpha_composite(img_type, (20, 20))
    font = ImageFont.truetype(nunito_light_path, 36)
    noto1 = ImageFont.truetype(noto_sans_demilight_path, 20)
    font2 = ImageFont.truetype(nunito_light_path, 18)
    font3 = ImageFont.truetype(nunito_light_path, 16)
    drawtext = ImageDraw.Draw(img)
    drawtext.text((20, 90), truncate_text(html2text(chart_name), 32), "#ffffff", font=noto1)
    drawtext.text((20, 110), score, "#ffffff", font=font)
    drawtext.text(
        (20, 155),
        f"Acc {100 * acc:.2f}%  Max Combo {details["maxCombo"]}  Rating {rt:.2f}",
        font=font3,
    )
    drawtext.text(
        (20, 180),
        f"Perfect {details["perfect"]}  Great {details["great"]}  Good {details["good"]}"
        f"\nBad {details["bad"]}  Miss {details["miss"]}",
        font=font3,
    )
    playtime = f"{playtime}  #{rank}"
    playtime_width = get_fontsize(font2, playtime)[0]
    songimg_width = 384
    drawtext.text(
        (songimg_width - playtime_width - 20, 25), playtime, "#ffffff", font=font2
    )
    type_ = str(difficulty)
    type_text = Image.new("RGBA", (32, 32))
    draw_typetext = ImageDraw.Draw(type_text)
    draw_typetext.text(
        ((32 - get_fontsize(font2, type_)[0]) / 2, 0), type_, "#ffffff", font=font2
    )
    img.alpha_composite(type_text, (23, 29))
    Logger.debug("Image generated: " + str(rank))
    return {int(rank): img}
