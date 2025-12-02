from PIL import Image, ImageDraw, ImageFont

from core.constants.path import noto_sans_demilight_path


def draw_scoreline_table(tap: int = 0,
                         hold: int = 0,
                         slide: int = 0,
                         touch: int = 0,
                         brk: int = 0,
                         mode: str = "0+"):
    total_notes = tap + 2 * hold + 3 * slide + touch + 5 * brk
    if total_notes == 0:
        base_fixup = None
    else:
        base_fixup = 100 / total_notes

    if brk == 0:
        bonus_fixup = None
    else:
        bonus_fixup = 1 / brk

    YELLOW = "#FFC107"
    ORANGE = "#FF9800"
    PINK = "#EC407A"
    GREEN = "#4CAF50"
    GREY = "#9E9E9E"

    header1 = ["TAP", "HOLD", "SLIDE", "TOUCH", "BREAK"]
    header2 = ["PERFECT", "GREAT", "GOOD", "MISS"]
    rows = ["TAP", "HOLD", "SLIDE", "TOUCH", "BREAK", "", ""]

    cell_w = 150
    cell_h = 60
    padding = 30
    gap = 20

    img_w = len(header1) * cell_w + padding * 2
    img_h = (len(rows) + 3) * cell_h + padding * 2 + gap

    img = Image.new("RGB", (img_w, img_h), (211, 211, 211))
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(noto_sans_demilight_path, 24)

    for i, text in enumerate(header1):
        x = padding + i * cell_w
        y = padding
        draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(0, 0, 0), width=2)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((x + (cell_w - w) / 2, y + (cell_h - h) / 2), text, fill=(0, 0, 0), font=font)

    draw.rectangle([padding, padding, padding + cell_w, padding + cell_h], outline=(0, 0, 0), width=2)

    values = [tap, hold, slide, touch, brk]
    for i, val in enumerate(values):
        x = padding + i * cell_w
        y = padding + cell_h
        draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(0, 0, 0), width=2)
        bbox = draw.textbbox((0, 0), str(val), font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((x + (cell_w - w) / 2, y + (cell_h - h) / 2), str(val), fill=(0, 0, 0), font=font)
    draw.rectangle([padding, padding + cell_h, padding + cell_w, padding + 2 * cell_h], outline=(0, 0, 0), width=2)

    offset_y = padding + 2 * cell_h + gap
    draw.rectangle([padding, offset_y, padding + cell_w, offset_y + cell_h], outline=(0, 0, 0), width=2)
    for i, text in enumerate(header2):
        x = padding + (i + 1) * cell_w
        y = offset_y
        color = [ORANGE, PINK, GREEN, GREY][i]
        draw.rectangle([x, y, x + cell_w, y + cell_h], fill=color, outline=(0, 0, 0), width=2)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((x + (cell_w - w) / 2, y + (cell_h - h) / 2), text, fill=(255, 255, 255), font=font)

    for i, text in enumerate(rows[:-3]):
        x = padding
        y = offset_y + (i + 1) * cell_h
        draw.rectangle([x, y, x + cell_w, y + cell_h], outline=(0, 0, 0), width=2)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text((x + (cell_w - w) / 2, y + (cell_h - h) / 2), text, fill=(0, 0, 0), font=font)

    x = padding
    y_start = offset_y + 5 * cell_h
    y_end = offset_y + 8 * cell_h
    draw.rectangle([x, y_start, x + cell_w, y_end], outline=(0, 0, 0), width=2)
    bbox = draw.textbbox((0, 0), "BREAK", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x + (cell_w - w) / 2, y_start + ((y_end - y_start) - h) / 2), "BREAK", fill=(0, 0, 0), font=font)

    note_counts = [tap, hold, slide, touch, brk]
    for row in range(len(rows)):
        for col in range(len(header2)):
            x = padding + (col + 1) * cell_w
            y = offset_y + (row + 1) * cell_h

            if row >= 4 and col in [2, 3]:
                if row == 4:
                    y_start = offset_y + 5 * cell_h
                    y_end = offset_y + 8 * cell_h
                    draw.rectangle([x, y_start, x + cell_w, y_end], fill=[GREEN, GREY]
                                   [col - 2], outline=(0, 0, 0), width=2)

                    if brk == 0:
                        text = "-"
                    else:
                        if col == 2:
                            value = 2 * base_fixup + 0.3 * bonus_fixup
                        elif col == 3:
                            value = 0

                        if mode == "100-":
                            max_base = 5 * base_fixup
                            base_part = value - (bonus_fixup if bonus_fixup else 0)
                            value = (base_part - max_base) + (bonus_fixup if bonus_fixup else 0)
                        elif mode == "101-":
                            max_total = 5 * base_fixup + (bonus_fixup if bonus_fixup else 0)
                            value = value - max_total

                        text = f"{value:.4f}%"

                    bbox = draw.textbbox((0, 0), text, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    draw.text((x + (cell_w - w) / 2, y_start + ((y_end - y_start) - h) / 2),
                              text, fill=(255, 255, 255), font=font)
                continue

            color = [ORANGE, PINK, GREEN, GREY][col]
            if col == 0 and row == 4:
                color = YELLOW
            draw.rectangle([x, y, x + cell_w, y + cell_h], fill=color, outline=(0, 0, 0), width=2)

            if row < 5 and note_counts[row] == 0:
                text = "-"
            else:
                try:
                    if row == 0:  # TAP
                        value = [base_fixup, 0.8 * base_fixup, 0.5 * base_fixup, 0][col]
                    elif row == 1:  # HOLD
                        value = [2 * base_fixup, 1.6 * base_fixup, base_fixup, 0][col]
                    elif row == 2:  # SLIDE
                        value = [3 * base_fixup, 2.4 * base_fixup, 1.5 * base_fixup, 0][col]
                    elif row == 3:  # TOUCH
                        value = [base_fixup, 0.8 * base_fixup, 0.5 * base_fixup, 0][col]
                    elif row == 4:  # BREAK 2600
                        value = [
                            5 * base_fixup + bonus_fixup,
                            4 * base_fixup + 0.4 * bonus_fixup,
                            2 * base_fixup + 0.3 * bonus_fixup,
                            0,
                        ][col]
                    elif row == 5:  # BREAK 2550
                        value = [
                            5 * base_fixup + 0.75 * bonus_fixup,
                            3 * base_fixup + 0.4 * bonus_fixup,
                            2 * base_fixup + 0.3 * bonus_fixup,
                            0,
                        ][col]
                    elif row == 6:  # BREAK 2500
                        value = [
                            5 * base_fixup + 0.5 * bonus_fixup,
                            2.5 * base_fixup + 0.4 * bonus_fixup,
                            2 * base_fixup + 0.3 * bonus_fixup,
                            0,
                        ][col]
                    else:
                        value = 0

                    if mode == "100-":
                        if row <= 3:  # TAP, HOLD, SLIDE, TOUCH
                            max_base = [base_fixup, 2 * base_fixup, 3 * base_fixup, base_fixup][row]
                            value -= max_base
                        elif row in [4, 5, 6]:  # BREAK 系列
                            max_base = 5 * base_fixup
                            base_part = value - bonus_fixup if bonus_fixup else value
                            value = (base_part - max_base) + (bonus_fixup if bonus_fixup else 0)
                    elif mode == "101-":
                        if row <= 3:
                            max_base = [base_fixup, 2 * base_fixup, 3 * base_fixup, base_fixup][row]
                            value -= max_base
                        elif row in [4, 5, 6]:
                            max_total = 5 * base_fixup + (bonus_fixup if bonus_fixup else 0)
                            value -= max_total

                    text = f"{value:.4f}%"
                except TypeError:
                    text = "-"

            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((x + (cell_w - w) / 2, y + (cell_h - h) / 2), text, fill=(255, 255, 255), font=font)

    font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
    draw.text(
        (5, img_h - 15), "Generated by Teahouse Studios \"AkariBot\"", (0, 0, 0), font=font
    )
    return img
