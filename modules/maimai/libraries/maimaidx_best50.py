from PIL import Image, ImageDraw, ImageFont

from core.builtins.bot import Bot
from core.constants.path import noto_sans_bold_path, noto_sans_demilight_path, noto_sans_symbol_path
from core.utils.func import truncate_text
from .maimaidx_apidata import get_record
from .maimaidx_mapping import (
    mai_cover_path,
    rate_mapping,
    combo_mapping,
    sync_mapping,
    diff_list,
)
from .maimaidx_music import TotalList
from .maimaidx_utils import compute_rating, calc_dxstar

total_list = TotalList()


class ChartInfo:
    def __init__(
        self,
        song_id: str,
        diff: int,
        chart_type: str,
        rating: int,
        achievement: float,
        dx_score: int,
        dx_score_max: int,
        combo: str,
        sync: str,
        rate: str,
        title: str,
        ds: float,
        level: str,
    ):
        self.song_id = song_id
        self.diff = diff
        self.chart_type = chart_type
        self.rating = compute_rating(ds, achievement)
        self.achievement = achievement
        self.dx_score = dx_score
        self.dx_score_max = dx_score_max
        self.combo = combo
        self.sync = sync
        self.rate = rate
        self.title = title
        self.ds = ds
        self.level = level

    def __str__(self):
        return f"{self.title:<50} [{self.chart_type}]{self.ds}\t{diff_list[self.diff]}\t{self.rating}"

    def __eq__(self, other):
        return self.rating == other.rating

    def __lt__(self, other):
        return self.rating < other.rating

    def __hash__(self):
        return hash(self.rating)

    @classmethod
    async def from_json(cls, data):
        music = (await total_list.get()).by_id(str(data["song_id"]))
        dx_score_max = sum(music["charts"][data["level_index"]]["notes"]) * 3
        return cls(
            song_id=data["song_id"],
            title=data["title"],
            diff=data["level_index"],
            ds=data["ds"],
            rating=data["ra"],
            dx_score=data["dxScore"],
            dx_score_max=dx_score_max,
            combo=combo_mapping.get(data["fc"], ""),
            sync=sync_mapping.get(data["fs"], ""),
            rate=rate_mapping.get(data["rate"], ""),
            level=data["level"],
            achievement=data["achievements"],
            chart_type=data["type"],
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
    def __init__(self, sd_best: BestList, dx_best: BestList, username: str):
        self.sd_best = sd_best
        self.dx_best = dx_best
        self.username = self._fullwidth_to_halfwidth(username)
        self.sd_rating = sum(compute_rating(c.ds, c.achievement) for c in sd_best)
        self.dx_rating = sum(compute_rating(c.ds, c.achievement) for c in dx_best)
        self.player_rating = self.sd_rating + self.dx_rating

        self.img = Image.new("RGBA", (860, 1300), color=(211, 211, 211, 255))  # 创建空白图像
        self.rows_image = [140 + 110 * i for i in range(7)] + [940 + 110 * i for i in range(3)]
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
        padding = 8
        text = f"RATING    {rating}"

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        rect = [x, y, x + text_width + padding * 2, y + text_height + padding * 2]

        if rating >= 12000:
            gradient_colors = DrawBest._get_rating_color(rating)
            gradient = Image.new("RGB", (rect[2] - rect[0], rect[3] - rect[1]))
            grad_draw = ImageDraw.Draw(gradient)
            width = gradient.width
            for i, color in enumerate(gradient_colors[:-1]):
                next_color = gradient_colors[i + 1]
                for x_pos in range(int(i * width / (len(gradient_colors) - 1)),
                                   int((i + 1) * width / (len(gradient_colors) - 1))):
                    r = int(color[0] + (next_color[0] - color[0]) * (x_pos - i * width /
                            (len(gradient_colors) - 1)) / (width / (len(gradient_colors) - 1)))
                    g = int(color[1] + (next_color[1] - color[1]) * (x_pos - i * width /
                            (len(gradient_colors) - 1)) / (width / (len(gradient_colors) - 1)))
                    b = int(color[2] + (next_color[2] - color[2]) * (x_pos - i * width /
                            (len(gradient_colors) - 1)) / (width / (len(gradient_colors) - 1)))
                    grad_draw.line([(x_pos, 0), (x_pos, gradient.height)], fill=(r, g, b))
            mask = Image.new("L", gradient.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, gradient.width, gradient.height], radius=10, fill=255)
            img.paste(gradient, (rect[0], rect[1]), mask)
        else:
            color = DrawBest._get_rating_color(rating)
            draw.rounded_rectangle(rect, radius=10, fill=color)

        text_color = (255, 255, 255) if rating >= 1000 else (0, 0, 0)
        draw.text((x + padding, y + padding - 2), text, fill=text_color, font=font)

    @staticmethod
    def _get_rating_color(rating: int):
        if rating >= 15000:
            color = [(255, 56, 56), (255, 235, 0), (129, 217, 85), (69, 174, 255), (186, 82, 255)]  # 彩
        elif rating >= 14500:
            color = [(248, 225, 67), (255, 250, 160), (248, 225, 67)]  # 白金
        elif rating >= 14000:
            color = [(210, 130, 16), (248, 225, 67), (210, 130, 16)]  # 金
        elif rating >= 13000:
            color = [(136, 144, 190), (182, 201, 241), (136, 144, 190)]  # 银
        elif rating >= 12000:
            color = [(206, 100, 30), (182, 201, 241), (206, 100, 30)]  # 铜
        elif rating >= 10000:
            color = (186, 82, 255)  # 紫
        elif rating >= 7000:
            color = (255, 56, 56)  # 红
        elif rating >= 4000:
            color = (255, 235, 0)  # 黄
        elif rating >= 2000:
            color = (129, 217, 85)  # 绿
        elif rating >= 1000:
            color = (69, 174, 255)  # 蓝
        else:
            color = (255, 255, 255)  # 白
        return color

    @staticmethod
    def _get_goal_color(goal: str):
        match goal:
            case "C" | "D":
                color = (206, 196, 204)
            case "B" | "BB" | "BBB":
                color = (69, 174, 255)
            case "A" | "AA" | "AAA":
                color = (255, 129, 141)
            case "S" | "S+" | "SS" | "SS+":
                color = (239, 243, 13)
            case "SSS":
                color = [(239, 243, 13), (69, 174, 255), (255, 129, 141)]
            case "SSS+":
                color = [(239, 243, 13), (69, 174, 255), (255, 129, 141), (239, 243, 13)]
            case "FC" | "FC+":
                color = (129, 217, 85)
            case "AP" | "AP+":
                color = (249, 128, 4)
            case "SYNC":
                color = (49, 195, 246)
            case "FS" | "FS+":
                color = (69, 174, 255)
            case "FDX" | "FDX+":
                color = (249, 128, 4)
            case "✦" | "✦✦":
                color = (129, 217, 85)
            case "✦✦✦" | "✦✦✦✦":
                color = (249, 128, 4)
            case "✦✦✦✦✦":
                color = (239, 243, 13)
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
            (217, 197, 233),
        ]
        level_triagle = [(item_weight, 0), (item_weight - 27, 0), (item_weight, 27)]
        ImageDraw.Draw(img)

        for num in range(min(len(self.sd_best), 35)):
            i = num // 5
            j = num % 5
            chart_info: ChartInfo = sd_best[num]
            cover_path = mai_cover_path / f"{chart_info.song_id}.png"
            if not cover_path.exists():
                cover_path = mai_cover_path / "0.png"

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
            temp_draw.text((7, 29), f"ID: {chart_info.song_id}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_bold_path, 18, encoding="utf-8")
            if chart_info.rate in ["SSS", "SSS+"]:
                x_ = 96
                for k, char in enumerate(chart_info.rate):
                    temp_draw.text((x_, 42), char, self._get_goal_color(chart_info.rate)[k], font)
                    x_ += font.getbbox(char)[2]
            else:
                temp_draw.text((96, 42), chart_info.rate, self._get_goal_color(chart_info.rate), font)
            font = ImageFont.truetype(noto_sans_bold_path, 12, encoding="utf-8")
            if chart_info.combo:
                temp_draw.text((80, 27), chart_info.combo, self._get_goal_color(chart_info.combo), font)
            if chart_info.sync:
                temp_draw.text((110, 27), chart_info.sync, self._get_goal_color(chart_info.sync), font)
            if chart_info.dx_score:
                font = ImageFont.truetype(
                    noto_sans_demilight_path, 12, encoding="utf-8"
                )
                temp_draw.text(
                    (7, 63),
                    f"{chart_info.dx_score}/{chart_info.dx_score_max}",
                    "white",
                    font,
                )
                font = ImageFont.truetype(noto_sans_symbol_path, 12, encoding="utf-8")
                dx_star = calc_dxstar(chart_info.dx_score, chart_info.dx_score_max)
                temp_draw.text(
                    (90, 61),
                    dx_star,
                    self._get_goal_color(dx_star),
                    font,
                )
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            temp_draw.text(
                (7, 80),
                f"{chart_info.ds} -> {compute_rating(chart_info.ds, chart_info.achievement)}",
                "white",
                font,
            )
            temp_draw.text((120, 80), f"#{num + 1}", "white", font)

            rec_base = Image.new("RGBA", (item_weight, item_height), "black")
            rec_base = rec_base.point(lambda p: int(p * 0.8))
            self.img.paste(rec_base, (self.columns_image[j + 1] + 5, self.rows_image[i] + 5))
            self.img.paste(temp, (self.columns_image[j + 1] + 4, self.rows_image[i] + 4))

        for num in range(min(len(self.dx_best), 15)):
            i = num // 5
            j = num % 5
            chart_info: ChartInfo = dx_best[num]
            cover_path = mai_cover_path / f"{chart_info.song_id}.png"
            if not cover_path.exists():
                cover_path = mai_cover_path / "0.png"

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
            temp_draw.text((7, 29), f"ID: {chart_info.song_id}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_bold_path, 18, encoding="utf-8")
            if chart_info.rate in ["SSS", "SSS+"]:
                x_ = 96
                for k, char in enumerate(chart_info.rate):
                    temp_draw.text((x_, 42), char, self._get_goal_color(chart_info.rate)[k], font)
                    x_ += font.getbbox(char)[2]
            else:
                temp_draw.text((96, 42), chart_info.rate, self._get_goal_color(chart_info.rate), font)
            font = ImageFont.truetype(noto_sans_bold_path, 12, encoding="utf-8")
            if chart_info.combo:
                temp_draw.text((80, 27), chart_info.combo, self._get_goal_color(chart_info.combo), font)
            if chart_info.sync:
                temp_draw.text((110, 27), chart_info.sync, self._get_goal_color(chart_info.sync), font)
            if chart_info.dx_score:
                font = ImageFont.truetype(
                    noto_sans_demilight_path, 12, encoding="utf-8"
                )
                temp_draw.text(
                    (7, 63),
                    f"{chart_info.dx_score}/{chart_info.dx_score_max}",
                    "white",
                    font,
                )
                font = ImageFont.truetype(noto_sans_symbol_path, 12, encoding="utf-8")
                dx_star = calc_dxstar(chart_info.dx_score, chart_info.dx_score_max)
                temp_draw.text(
                    (90, 61),
                    dx_star,
                    self._get_goal_color(dx_star),
                    font,
                )
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            temp_draw.text(
                (7, 80),
                f"{chart_info.ds} -> {compute_rating(chart_info.ds, chart_info.achievement)}",
                "white",
                font,
            )
            temp_draw.text((120, 80), f"#{num + 1}", "white", font)

            rec_base = Image.new("RGBA", (item_weight, item_height), "black")
            rec_base = rec_base.point(lambda p: int(p * 0.8))
            self.img.paste(
                rec_base, (self.columns_image[j + 1] + 5, self.rows_image[i + 7] + 5)
            )
            self.img.paste(
                temp, (self.columns_image[j + 1] + 4, self.rows_image[i + 7] + 4)
            )

    def draw(self):
        img_draw = ImageDraw.Draw(self.img)
        font = ImageFont.truetype(noto_sans_demilight_path, 30, encoding="utf-8")
        img_draw.text((34, 24), " ".join(self.username), fill="black", font=font)
        font = ImageFont.truetype(noto_sans_bold_path, 16, encoding="utf-8")
        self._draw_rating(self.img, img_draw, (34, 64), self.player_rating, font)
        font = ImageFont.truetype(noto_sans_demilight_path, 20, encoding="utf-8")
        img_draw.text((34, 114), f"PAST ({self.sd_rating})", fill="black", font=font)
        img_draw.text((34, 914), f"NEW ({self.dx_rating})", fill="black", font=font)
        self._draw_best_list(self.img, self.sd_best, self.dx_best)

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        img_draw.text(
            (5, 1285), "Generated by Teahouse Studios \"AkariBot\"", "black", font=font
        )

    def get_dir(self):
        return self.img


async def generate(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Image.Image | None:
    resp = await get_record(msg, payload, use_cache)
    sd_best = BestList(35)
    dx_best = BestList(15)
    dx: list[dict] = resp["charts"]["dx"]
    sd: list[dict] = resp["charts"]["sd"]
    for c in sd:
        sd_best.push(await ChartInfo.from_json(c))
    for c in dx:
        dx_best.push(await ChartInfo.from_json(c))
    pic = DrawBest(sd_best, dx_best, resp["nickname"]).get_dir()
    return pic
