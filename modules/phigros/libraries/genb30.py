from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from core.builtins.bot import Bot
from core.constants.path import assets_path, noto_sans_demilight_path, noto_sans_bold_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.message import truncate_text
from .record import get_game_record

pgr_assets_path = assets_path / "modules" / "phigros"

saira_regular_path = pgr_assets_path / "Saira Regular.ttf"

levels = {"EZ": 0, "HD": 1, "IN": 2, "AT": 3}


def get_song_rank(song_score: int, song_fc: bool):
    if song_score == 1000000:
        return "Φ", "#FFD700"
    if song_fc and song_score != 1000000:
        return "V", "#1E90FF"
    if 960000 <= song_score <= 999999:
        return "V", "#FFFFFF"
    if 920000 <= song_score <= 959999:
        return "S", "#FFFFFF"
    if 880000 <= song_score <= 919999:
        return "A", "#FFFFFF"
    if 820000 <= song_score <= 879999:
        return "B", "#FFFFFF"
    if 700000 <= song_score <= 819999:
        return "C", "#FFFFFF"
    if 0 <= song_score <= 699999:
        return "F", "#FFFFFF"
    return "", "#FFFFFF"


async def get_b30(msg: Bot.MessageSession, username: str, session_token: str):
    game_records: dict = await get_game_record(msg, session_token)
    result = []

    for song_id, song_data in game_records.items():
        name = song_data["name"]
        for diff, info in song_data["diff"].items():
            result.append((song_id, diff, name, info))

    result.sort(key=lambda x: x[3]["rks"], reverse=True)

    phi_list = [s for s in result if s[3]["score"] == 1000000]
    p3_data = sorted(phi_list, key=lambda x: x[3]["rks"], reverse=True)[:3]
    b27_data = result[:27]

    all_rks = [i[3]["rks"] for i in (p3_data + b27_data)]
    if len(all_rks) < 30:
        all_rks += [0] * (30 - len(all_rks))
    avg_acc = round(sum(all_rks) / len(all_rks), 2)

    Logger.debug(f"P3 Data: {p3_data}")
    Logger.debug(f"B27 Data: {b27_data}")

    return draw_b30(username, avg_acc, p3_data, b27_data)


def draw_b30(username, rks_acc, p3data, b27data):
    card_w, card_h = 384, 240
    cols, rows = 3, 10
    margin_top = 100
    margin_bottom = 30
    gap_between_p3_b27 = 30

    width = card_w * cols + 30
    height = card_h * rows + margin_top + gap_between_p3_b27 + margin_bottom
    final_img = Image.new("RGBA", (width, height), "#1e2129")

    font1 = ImageFont.truetype(saira_regular_path, 16)
    font2 = ImageFont.truetype(saira_regular_path, 20)
    font3 = ImageFont.truetype(saira_regular_path, 24)
    font4 = ImageFont.truetype(saira_regular_path, 28)
    noto3 = ImageFont.truetype(noto_sans_demilight_path, 24)
    noto_rank = ImageFont.truetype(noto_sans_bold_path, 60)

    drawtext = ImageDraw.Draw(final_img)

    if any(ord(c) > 127 for c in username):
        selected_font = noto3
    else:
        selected_font = font3

    text1_width = selected_font.getbbox(username)[2]
    drawtext.text(
        (final_img.width - text1_width - 20, 24),
        username,
        "#ffffff",
        font=selected_font
    )
    rks_text = f"{rks_acc:.2f}"
    text2_width = font2.getbbox(rks_text)[2]
    drawtext.text(
        (final_img.width - text2_width - 20, 52), rks_text, "#ffffff", font=font2
    )

    def draw_card(song_, x, y, label, phi=False):
        try:
            song_id = song_[0]
            song_level = song_[1]
            song_name = song_[2]
            song_score = song_[3]["score"]
            song_rks = song_[3]["rks"]
            song_acc = song_[3]["accuracy"]
            song_base_rks = song_[3]["base_rks"]
            song_fc = song_[3]["full_combo"]

            if not song_id:
                cardimg = Image.new("RGBA", (card_w, card_h), "black")
            else:
                imgpath = pgr_assets_path / "illustration" / f"{song_id.lower()}.png"
                if not imgpath.exists():
                    cardimg = Image.new("RGBA", (card_w, card_h), "black")
                else:
                    cardimg = Image.open(imgpath)
                    if cardimg.mode != "RGBA":
                        cardimg = cardimg.convert("RGBA")
                    downlight = ImageEnhance.Brightness(cardimg)
                    img_size = downlight.image.size
                    resize_multiplier = card_w / img_size[0]
                    img_h = int(img_size[1] * resize_multiplier)
                    if img_h < card_h:
                        resize_multiplier = card_h / img_size[1]
                        resize_img_w = int(img_size[0] * resize_multiplier)
                        resize_img_h = int(img_size[1] * resize_multiplier)
                        crop_start_x = int((resize_img_w - card_w) / 2)
                        crop_start_y = int((resize_img_h - card_h) / 2)
                        cardimg = (
                            downlight.enhance(0.5)
                            .resize((resize_img_w, resize_img_h))
                            .crop(
                                (
                                    crop_start_x,
                                    crop_start_y,
                                    card_w + crop_start_x,
                                    card_h + crop_start_y,
                                )
                            )
                        )
                    elif img_h > card_h:
                        crop_start_y = int((img_h - card_h) / 2)
                        cardimg = (
                            downlight.enhance(0.5)
                            .resize((card_w, img_h))
                            .crop((0, crop_start_y, card_w, card_h + crop_start_y))
                        )
                    else:
                        cardimg = downlight.enhance(0.5).resize((card_w, img_h))

            triangle_img = Image.new("RGBA", (100, 100), "rgba(0,0,0,0)")
            draw = ImageDraw.Draw(triangle_img)
            draw.polygon(
                [(0, 0), (0, 100), (100, 0)],
                fill=["#11b231", "#0273b7", "#cd1314", "#383838"][levels[song_level]],
            )
            text_img = Image.new("RGBA", (70, 70), "rgba(0,0,0,0)")
            text_draw = ImageDraw.Draw(text_img)
            text1 = ["EZ", "HD", "IN", "AT"][levels[song_level]]
            text2 = str(round(song_base_rks, 1))
            text_size1 = font2.getbbox(text1)
            text_size2 = font1.getbbox(text2)
            text_draw.text(
                (
                    (text_img.width - text_size1[2]) / 2,
                    (text_img.height - text_size1[3]) / 2,
                ),
                text1,
                font=font2,
                fill="#FFFFFF",
            )
            text_draw.text(
                (
                    (text_img.width - text_size2[2]) / 2,
                    (text_img.height - text_size2[3]) / 2 + 20,
                ),
                text2,
                font=font1,
                fill="#FFFFFF",
            )
            triangle_img.alpha_composite(text_img.rotate(45, expand=True), (-25, -25))
            cardimg.alpha_composite(triangle_img.resize((75, 75)), (0, 0))

            draw_card = ImageDraw.Draw(cardimg)
            draw_card.text((20, 120), truncate_text(song_name, 28), "#ffffff", font=noto3)
            draw_card.text((20, 150), str(song_score), "#ffffff", font=font4)
            draw_card.text((20, 190), f"{song_acc:.2f}%", "#ffffff", font=font1)
            draw_card.text((120, 190), f"rks: {song_rks:.2f}", "#ffffff", font=font1)

            rank_symbol, rank_color = get_song_rank(song_score, song_fc)
            draw_card.text((300, 155), rank_symbol, rank_color, font=noto_rank)

            text_w, _ = font2.getbbox(label)[2:]
            draw_card.text(
                (card_w - text_w - 15, 10),
                label,
                "#FFD700" if phi else "#ffffff",
                font=font2,
            )

            final_img.alpha_composite(cardimg, (x, y))
        except Exception:
            Logger.exception()

    for idx, song in enumerate(p3data):
        x = 15 + card_w * idx
        y = margin_top
        draw_card(song, x, y, f"P{idx + 1}", phi=True)

    dash_y = margin_top + card_h + gap_between_p3_b27 // 2
    x_start, x_end = 15, width - 15
    dash_length, gap_length = 10, 10
    x = x_start
    while x < x_end:
        drawtext.line([(x, dash_y), (min(x + dash_length, x_end), dash_y)], fill="#FFFFFF", width=2)
        x += dash_length + gap_length

    for idx, song in enumerate(b27data):
        row = idx // cols
        col = idx % cols
        x = 15 + card_w * col
        y = margin_top + card_h + gap_between_p3_b27 + row * card_h
        draw_card(song, x, y, f"#{idx + 1}")

    generated_text = "Generated by Teahouse Studios \"AkariBot\""
    _, text_height = font1.getbbox(generated_text)[2:]
    drawtext.text(
        (20, final_img.height - text_height - 5),
        generated_text,
        "#ffffff",
        font=font1
    )

    savefilename = f"{random_cache_path()}.png"
    final_img.convert("RGB").save(savefilename)
    return savefilename
