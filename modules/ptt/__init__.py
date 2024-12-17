import os

from PIL import Image, ImageDraw, ImageFont

from core.builtins import Bot, Image as BImage
from core.component import module
from core.constants.path import assets_path
from core.utils.cache import random_cache_path
from core.utils.image import get_fontsize

arc_assets_path = os.path.join(assets_path, "arcaea")


p = module("ptt", developers=["OasisAkari"], doc=True)


@p.command("<ptt> {{ptt.help}}")
async def pttimg(msg: Bot.MessageSession, ptt: str):
    if ptt == "--":
        ptt = -1
    else:
        try:
            ptt = float(ptt)
        except ValueError:
            await msg.finish(msg.locale.t("ptt.message.invalid"))
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
        pttimg = "off"
    pttimgr = Image.open(
        os.path.join(arc_assets_path, "ptt", f"rating_{str(pttimg)}.png")
    )
    ptttext = Image.new("RGBA", (119, 119))
    font1 = ImageFont.truetype(
        os.path.join(arc_assets_path, "Fonts", "Exo-SemiBold.ttf"), 49
    )
    font2 = ImageFont.truetype(
        os.path.join(arc_assets_path, "Fonts", "Exo-SemiBold.ttf"), 33
    )
    if 0 <= ptt <= 99.99:
        rawptt = str(ptt).split(".")
        if len(rawptt) < 2:
            ptt1 = rawptt[0]
            ptt2 = "00"
        else:
            ptt1 = rawptt[0]
            ptt2 = rawptt[1][:2]
            if len(ptt2) < 2:
                ptt2 += "0"
        ptttext_width, ptttext_height = ptttext.size
        font1_width, font1_height = get_fontsize(font1, ptt1 + ".")
        font2_width, font2_height = get_fontsize(font2, ptt2)
        pttimg = Image.new("RGBA", (font1_width + font2_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        stroke_color = "#52495d"
        if int(ptt1) >= 13:
            stroke_color = "#81122F"
        drawptt.text(
            (0, 0),
            ptt1 + ".",
            "white",
            font=font1,
            stroke_width=3,
            stroke_fill=stroke_color,
        )
        drawptt.text(
            (font1_width, int(int(font1_height) - int(font2_height))),
            ptt2,
            "white",
            font=font2,
            stroke_width=3,
            stroke_fill=stroke_color,
        )
    elif ptt == -1:
        ptt = "--"
        ptttext_width, ptttext_height = ptttext.size
        font1_width, font1_height = get_fontsize(font1, ptt)
        pttimg = Image.new("RGBA", (font1_width + 6, font1_height + 6))
        drawptt = ImageDraw.Draw(pttimg)
        drawptt.text(
            (0, 0), ptt, "white", font=font1, stroke_width=3, stroke_fill="#52495d"
        )
    else:
        return await msg.finish(msg.locale.t("ptt.message.invalid"))
    pttimg_width, pttimg_height = pttimg.size
    ptttext.alpha_composite(
        pttimg,
        (
            int((ptttext_width - pttimg_width) / 2),
            int((ptttext_height - pttimg_height) / 2) - 11,
        ),
    )
    ptttext = ptttext.resize(pttimgr.size)
    pttimgr.alpha_composite(ptttext, (0, 0))
    savepath = f"{random_cache_path()}.png"
    pttimgr.save(savepath)
    await msg.finish([BImage(path=savepath)])
