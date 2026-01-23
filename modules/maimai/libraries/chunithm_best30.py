from typing import Any

from PIL import Image, ImageDraw, ImageFont

from core.builtins.bot import Bot
from core.constants.path import noto_sans_bold_path, noto_sans_demilight_path
from core.utils.func import truncate_text
from .chunithm_apidata import get_record_df, get_record_lx
from .chunithm_mapping import (
    chu_cover_path,
    score_to_rate,
    combo_mapping,
    diff_list
)
from .chunithm_music import TotalList

total_list = TotalList()


class ChartInfo:
    def __init__(
        self,
        mid: str,
        diff: int,
        ra: float,
        score: int,
        fc: str,
        title: str,
        ds: float,
        level: str,
        rate: str
    ):
        self.mid = mid
        self.diff = diff
        self.ra = ra
        self.score = score
        self.fc = fc
        self.title = title
        self.ds = ds
        self.level = level
        self.rate = rate

    def __str__(self):
        return f"{self.title:<50} {self.ds}\t{diff_list[self.diff]}\t{self.ra}"

    def __eq__(self, other):
        return self.ra == other.ra

    def __lt__(self, other):
        return self.ra < other.ra

    def __hash__(self):
        return hash(self.ra)

    @classmethod
    async def from_json(cls, data):
        for sr, r in score_to_rate.items():
            if sr[0] <= data["score"] <= sr[1]:
                rate = r
                break
        else:
            rate = ""

        return cls(
            mid=data["mid"],
            title=data["title"],
            diff=data["level_index"],
            ds=data["ds"],
            ra=data["ra"],
            fc=combo_mapping.get(data["fc"], ""),
            level=data["level"],
            score=data["score"],
            rate=rate
        )


class BestList:
    def __init__(self, size: int):
        self._data = []
        self._size = size

    def push(self, chart: ChartInfo):
        if len(self._data) >= self._size and chart < self._data[-1]:
            return
        self._data.append(chart)
        self._data.sort(reverse=True)
        self._data = self._data[:self._size]

    def pop(self):
        if self._data:
            self._data.pop()

    def __len__(self):
        return len(self._data)

    def __getitem__(self, index):
        return self._data[index]

    def __str__(self):
        return "[\n\t" + ", \n\t".join(map(str, self._data)) + "\n]"


class DrawBest:
    def __init__(self, best_30: BestList, new_20: BestList, username: str, rating: float, source: str):
        self.best_30 = best_30
        self.new_20 = new_20
        self.username = self._fullwidth_to_halfwidth(username)
        self.source = source
        self.player_rating = 0
        self.b30_rating = sum(c.ra for c in best_30) / len(best_30) if len(best_30) != 0 else 0.0
        self.n20_rating = sum(c.ra for c in new_20) / len(new_20) if len(new_20) != 0 else 0.0
        self.player_rating = rating

        self.img = Image.new("RGBA", (860, 1300), color=(211, 211, 211, 255))  # 创建空白图像
        self.rows_image = [140 + 110 * i for i in range(6)] + [830 + 110 * i for i in range(4)]
        self.columns_image = [30] + [30 + 160 * i for i in range(5)]

        self.draw()

    @staticmethod
    def _fullwidth_to_halfwidth(text: str) -> str:
        return "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in text)

    @staticmethod
    def _resize_image(img: Image.Image, scale: float) -> Image.Image:
        return img.resize((int(img.width * scale), int(img.height * scale)))

    @staticmethod
    def _draw_rating(img, draw, position, rating, font):
        x, y = position
        text = f"RATING    {rating:.2f}"

        padding = 2
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0] + 2 * padding
        text_height = bbox[3] - bbox[1] + 2 * padding

        outline_width = 1
        outline_color = (0, 0, 0)

        if rating >= 16.00:
            gradient_colors = DrawBest._get_rating_color(rating)
            gradient = Image.new("RGB", (text_width, text_height))
            grad_draw = ImageDraw.Draw(gradient)
            for y_pos in range(text_height):
                t = y_pos / (text_height - 1)
                n = len(gradient_colors) - 1
                segment = t * n
                i = int(segment)
                t_seg = segment - i
                if i >= n:
                    i = n - 1
                    t_seg = 1
                c0 = gradient_colors[i]
                c1 = gradient_colors[i + 1]
                r = int(c0[0] + (c1[0] - c0[0]) * t_seg)
                g = int(c0[1] + (c1[1] - c0[1]) * t_seg)
                b = int(c0[2] + (c1[2] - c0[2]) * t_seg)
                grad_draw.line([(0, y_pos), (text_width, y_pos)], fill=(r, g, b))

            mask = Image.new("L", (text_width, text_height), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.text((0, 0), text, font=font, fill=255)

            for dx in [-outline_width, 0, outline_width]:
                for dy in [-outline_width, 0, outline_width]:
                    if dx != 0 or dy != 0:
                        temp_mask = Image.new("L", (text_width, text_height), 0)
                        temp_draw = ImageDraw.Draw(temp_mask)
                        temp_draw.text((dx, dy), text, font=font, fill=255)
                        img.paste(outline_color, (x, y), temp_mask)

            img.paste(gradient, (x, y), mask)
        else:
            color = DrawBest._get_rating_color(rating)
            for dx in [-outline_width, 0, outline_width]:
                for dy in [-outline_width, 0, outline_width]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            draw.text((x, y), text, font=font, fill=color)

    @staticmethod
    def _get_rating_color(rating: float):
        if rating >= 16.00:
            color = [(11, 229, 186), (60, 249, 25), (244, 222, 49), (255, 235, 238), (42, 201, 240)]  # 彩
        elif rating >= 15.25:
            color = (255, 255, 224)  # 白金
        elif rating >= 14.50:
            color = (255, 215, 0)  # 金
        elif rating >= 13.25:
            color = (202, 242, 255)  # 银
        elif rating >= 12.00:
            color = (150, 107, 231)  # 铜
        elif rating >= 10.00:
            color = (128, 0, 128)  # 紫
        elif rating >= 7.00:
            color = (255, 0, 0)  # 红
        elif rating >= 4.00:
            color = (255, 165, 0)  # 橙
        elif rating >= 0.00:
            color = (0, 128, 0)  # 绿
        else:
            color = (0, 0, 0)
        return color

    @staticmethod
    def _get_goal_color(goal: str):
        match goal:
            case "C" | "D":
                color = (206, 196, 204)
            case "B" | "BB" | "BBB":
                color = (202, 242, 255)
            case "A" | "AA" | "AAA":
                color = (255, 215, 0)
            case "S" | "S+" | "SS" | "SS+" | "SSS" | "SSS+":
                color = (255, 255, 224)
            case "FULL COMBO":
                color = (255, 215, 0)
            case "ALL JUSTICE":
                color = (255, 255, 224)
            case _:
                color = (255, 255, 255)
        return color

    def _draw_best_list(self, img: Image.Image, sd_best: BestList, dx_best: BestList):
        item_weight = 150
        item_height = 100
        color = [
            (69, 193, 36),
            (255, 186, 1),
            (255, 90, 102),
            (134, 49, 200),
            (25, 25, 25),
        ]
        level_triagle = [(item_weight, 0), (item_weight - 27, 0), (item_weight, 27)]
        ImageDraw.Draw(img)

        for num in range(min(len(self.best_30), 30)):
            i = num // 5
            j = num % 5
            chart_info: ChartInfo = sd_best[num]
            cover_path = chu_cover_path / f"{chart_info.mid}.png"

            if cover_path.exists():
                temp = Image.open(cover_path).convert("RGBA")
                temp = self._resize_image(temp, item_weight / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - item_height) / 2, item_weight, (temp.size[1] + item_height) / 2)
                )
                overlay = Image.new("RGBA", temp.size, (0, 0, 0, 100))
                temp = Image.alpha_composite(temp, overlay)
            else:
                temp = Image.new("RGBA", (item_weight, item_height), (111, 111, 111, 255))

            temp_draw = ImageDraw.Draw(temp)
            temp_draw.polygon(level_triagle, color[chart_info.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = truncate_text(chart_info.title, 12)
            temp_draw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            temp_draw.text((7, 29), f"ID: {chart_info.mid}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.score:,}", "white", font)
            font = ImageFont.truetype(noto_sans_bold_path, 18, encoding="utf-8")
            temp_draw.text((96, 42), chart_info.rate, self._get_goal_color(chart_info.rate), font)
            font = ImageFont.truetype(noto_sans_bold_path, 12, encoding="utf-8")
            if chart_info.fc:
                temp_draw.text((7, 64), chart_info.fc, self._get_goal_color(chart_info.fc), font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            temp_draw.text(
                (7, 80),
                f"{chart_info.ds} -> {chart_info.ra:.2f}",
                "white",
                font,
            )
            temp_draw.text((120, 80), f"#{num + 1}", "white", font)

            rec_base = Image.new("RGBA", (item_weight, item_height), "black")
            rec_base = rec_base.point(lambda p: int(p * 0.8))
            self.img.paste(rec_base, (self.columns_image[j + 1] + 5, self.rows_image[i] + 5))
            self.img.paste(temp, (self.columns_image[j + 1] + 4, self.rows_image[i] + 4))

        for num in range(min(len(self.new_20), 20)):
            i = num // 5
            j = num % 5
            chart_info: ChartInfo = dx_best[num]
            cover_path = chu_cover_path / f"{chart_info.mid}.png"
            if cover_path.exists():
                temp = Image.open(cover_path).convert("RGBA")
                temp = self._resize_image(temp, item_weight / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - item_height) / 2, item_weight, (temp.size[1] + item_height) / 2)
                )
                overlay = Image.new("RGBA", temp.size, (0, 0, 0, 100))
                temp = Image.alpha_composite(temp, overlay)
            else:
                temp = Image.new("RGBA", (item_weight, item_height), (111, 111, 111, 255))

            temp_draw = ImageDraw.Draw(temp)
            temp_draw.polygon(level_triagle, color[chart_info.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = truncate_text(chart_info.title, 12)
            temp_draw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            temp_draw.text((7, 29), f"ID: {chart_info.mid}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.score:,}", "white", font)
            font = ImageFont.truetype(noto_sans_bold_path, 18, encoding="utf-8")
            temp_draw.text((96, 42), chart_info.rate, self._get_goal_color(chart_info.rate), font)
            font = ImageFont.truetype(noto_sans_bold_path, 12, encoding="utf-8")
            if chart_info.fc:
                temp_draw.text((7, 64), chart_info.fc, self._get_goal_color(chart_info.fc), font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            temp_draw.text(
                (7, 80),
                f"{chart_info.ds} -> {chart_info.ra:.2f}",
                "white",
                font,
            )
            temp_draw.text((120, 80), f"#{num + 1}", "white", font)

            rec_base = Image.new("RGBA", (item_weight, item_height), "black")
            rec_base = rec_base.point(lambda p: int(p * 0.8))
            self.img.paste(
                rec_base, (self.columns_image[j + 1] + 5, self.rows_image[i + 6] + 5)
            )
            self.img.paste(
                temp, (self.columns_image[j + 1] + 4, self.rows_image[i + 6] + 4)
            )

    def draw(self):
        img_draw = ImageDraw.Draw(self.img)
        font = ImageFont.truetype(noto_sans_demilight_path, 30, encoding="utf-8")
        img_draw.text((34, 24), " ".join(self.username), fill="black", font=font)
        font = ImageFont.truetype(noto_sans_demilight_path, 24, encoding="utf-8")
        img_draw.text((512, 60), f"API Source: {self.source}", fill="black", font=font)
        font = ImageFont.truetype(noto_sans_bold_path, 16, encoding="utf-8")
        self._draw_rating(self.img, img_draw, (38, 64), self.player_rating, font)
        font = ImageFont.truetype(noto_sans_demilight_path, 20, encoding="utf-8")
        img_draw.text((34, 114), f"BEST ({self.b30_rating:.2f})", fill="black", font=font)
        img_draw.text((34, 804), f"NEW ({self.n20_rating:.2f})", fill="black", font=font)
        self._draw_best_list(self.img, self.best_30, self.new_20)

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        img_draw.text(
            (5, 1285), "Generated by Teahouse Studios \"AkariBot\"", "black", font=font
        )

    def get_dir(self):
        return self.img


async def generate(msg: Bot.MessageSession, token: Any = None, source: str = "Lxns", use_cache: bool = True) -> Image.Image | None:
    if source == "Lxns":
        resp = await get_record_lx(msg, token, use_cache)
    else:
        resp = await get_record_df(msg, token, use_cache)
    best = BestList(30)
    new = BestList(20)
    b30: list[dict] = resp["records"]["b30"]
    n20: list[dict] = resp["records"]["n20"]
    for c in b30:
        best.push(await ChartInfo.from_json(c))
    for c in n20:
        new.push(await ChartInfo.from_json(c))
    pic = DrawBest(best, new, resp["nickname"], resp["rating"], source).get_dir()
    return pic
