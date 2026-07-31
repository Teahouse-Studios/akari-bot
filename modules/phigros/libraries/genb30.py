from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from core.builtins.bot import Bot
from core.constants.path import noto_sans_demilight_path, noto_sans_bold_path
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.func import truncate_text

from .PhiCloudActionAsync.ActionLib import getBest
from .assets import illustration_path, load_song_info
from .record import get_records, get_save

pgr_assets_path = Path(__file__).parent.parent / "assets"
saira_regular_path = pgr_assets_path / "Saira Regular.ttf"

LEVEL_INDEX = {"EZ": 0, "HD": 1, "IN": 2, "AT": 3}
LEVEL_COLORS = ("#11b231", "#0273b7", "#cd1314", "#383838")


def get_song_rank(score: int, fc: bool) -> tuple[str, str]:
    """按分数与 Full Combo 状态判定评级与配色。

    :param score: 分数。
    :param fc: 是否 Full Combo。
    """
    if score == 1000000:
        return "Φ", "#FFD700"
    if fc:
        return "V", "#1E90FF"
    if score >= 960000:
        return "V", "#FFFFFF"
    if score >= 920000:
        return "S", "#FFFFFF"
    if score >= 880000:
        return "A", "#FFFFFF"
    if score >= 820000:
        return "B", "#FFFFFF"
    if score >= 700000:
        return "C", "#FFFFFF"
    if score >= 0:
        return "F", "#FFFFFF"
    return "", "#FFFFFF"


async def get_b30(msg: Bot.MessageSession, bind_info) -> str:
    """生成 B30 图。

    :param msg: 消息会话。
    :param bind_info: 绑定信息记录。
    :return: 生成的图片路径。
    """
    song_info = load_song_info()
    save_data, summary = await get_save(msg, bind_info)
    records = get_records(save_data, song_info)

    # Legacy 谱面不计入 rks，卡片的难度标签与配色也只有四档，故在挑选前滤除。
    filtered = {
        song_id: {level: record for level, record in levels.items() if level in LEVEL_INDEX}
        for song_id, levels in records.items()
    }
    best = getBest(filtered, phi_count=3, best_count=27)

    Logger.debug(f"Phigros phi count: {len(best['phi'])}, best count: {len(best['best'])}")
    return draw_b30(bind_info.username, summary["rks"], best["phi"], best["best"], song_info)


def draw_b30(
    username: str,
    rks: float,
    phi_records: list[dict],
    best_records: list[dict],
    song_info: dict,
) -> str:
    """绘制 B30 图。

    :param username: 玩家昵称。
    :param rks: 官方 rks。
    :param phi_records: phi 榜记录。
    :param best_records: best 榜记录。
    :param song_info: 曲目信息结构。
    :return: 生成的图片路径。
    """
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

    selected_font = noto3 if any(ord(c) > 127 for c in username) else font3
    text1_width = selected_font.getbbox(username)[2]
    drawtext.text((final_img.width - text1_width - 20, 24), username, "#ffffff", font=selected_font)
    rks_text = f"{rks:.2f}"
    text2_width = font2.getbbox(rks_text)[2]
    drawtext.text((final_img.width - text2_width - 20, 52), rks_text, "#ffffff", font=font2)

    def draw_card(record: dict, x: int, y: int, label: str, phi: bool = False):
        try:
            song_id = record["name"]
            level = record["level"]
            song_name = song_info.get(song_id, {}).get("name", song_id.split(".")[0])
            score = record["score"]
            acc = record["acc"]
            song_rks = record["rks"]
            difficulty = record["difficulty"]
            fc = bool(record["fc"])

            imgpath = illustration_path(song_id)
            if not imgpath:
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
                        .crop((crop_start_x, crop_start_y, card_w + crop_start_x, card_h + crop_start_y))
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

            level_index = LEVEL_INDEX[level]
            triangle_img = Image.new("RGBA", (100, 100), "rgba(0,0,0,0)")
            draw = ImageDraw.Draw(triangle_img)
            draw.polygon([(0, 0), (0, 100), (100, 0)], fill=LEVEL_COLORS[level_index])

            text_img = Image.new("RGBA", (70, 70), "rgba(0,0,0,0)")
            text_draw = ImageDraw.Draw(text_img)
            text2 = str(round(difficulty, 1))
            text_size1 = font2.getbbox(level)
            text_size2 = font1.getbbox(text2)
            text_draw.text(
                ((text_img.width - text_size1[2]) / 2, (text_img.height - text_size1[3]) / 2),
                level,
                font=font2,
                fill="#FFFFFF",
            )
            text_draw.text(
                ((text_img.width - text_size2[2]) / 2, (text_img.height - text_size2[3]) / 2 + 20),
                text2,
                font=font1,
                fill="#FFFFFF",
            )
            triangle_img.alpha_composite(text_img.rotate(45, expand=True), (-25, -25))
            cardimg.alpha_composite(triangle_img.resize((75, 75)), (0, 0))

            draw_on_card = ImageDraw.Draw(cardimg)
            draw_on_card.text((20, 120), truncate_text(song_name, 28), "#ffffff", font=noto3)
            draw_on_card.text((20, 150), str(score), "#ffffff", font=font4)
            draw_on_card.text((20, 190), f"{acc:.2f}%", "#ffffff", font=font1)
            draw_on_card.text((120, 190), f"rks: {song_rks:.2f}", "#ffffff", font=font1)

            rank_symbol, rank_color = get_song_rank(score, fc)
            draw_on_card.text((300, 155), rank_symbol, rank_color, font=noto_rank)

            text_w = font2.getbbox(label)[2]
            draw_on_card.text((card_w - text_w - 15, 10), label, "#FFD700" if phi else "#ffffff", font=font2)

            final_img.alpha_composite(cardimg, (x, y))
        except Exception:
            Logger.exception()

    for idx, record in enumerate(phi_records):
        draw_card(record, 15 + card_w * idx, margin_top, f"P{idx + 1}", phi=True)

    dash_y = margin_top + card_h + gap_between_p3_b27 // 2
    x_start, x_end = 15, width - 15
    dash_length, gap_length = 10, 10
    x = x_start
    while x < x_end:
        drawtext.line([(x, dash_y), (min(x + dash_length, x_end), dash_y)], fill="#FFFFFF", width=2)
        x += dash_length + gap_length

    for idx, record in enumerate(best_records):
        row = idx // cols
        col = idx % cols
        x = 15 + card_w * col
        y = margin_top + card_h + gap_between_p3_b27 + row * card_h
        draw_card(record, x, y, f"#{idx + 1}")

    generated_text = 'Generated by Teahouse Studios "AkariBot"'
    text_height = font1.getbbox(generated_text)[3]
    drawtext.text((20, final_img.height - text_height - 5), generated_text, "#ffffff", font=font1)

    savefilename = f"{random_cache_path()}.png"
    final_img.convert("RGB").save(savefilename)
    return savefilename
