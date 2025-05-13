import os
from typing import Optional, Dict, List

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from core.builtins import Bot
from core.constants.path import noto_sans_demilight_path, noto_sans_symbol_path
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
            cover_path = os.path.join(mai_cover_path, f"{chart_info.song_id}.png")
            if not os.path.exists(cover_path):
                cover_path = os.path.join(mai_cover_path, "0.png")

            if os.path.exists(cover_path):
                temp = Image.open(cover_path).convert("RGB")
                temp = self._resize_image(temp, item_weight / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - item_height) / 2, item_weight, (temp.size[1] + item_height) / 2)
                )
                temp = temp.filter(ImageFilter.GaussianBlur(2))
                temp = temp.point(lambda p: int(p * 0.72))
            else:
                temp = Image.new("RGB", (int(item_weight), int(item_height)), (111, 111, 111, 255))

            temp_draw = ImageDraw.Draw(temp)
            temp_draw.polygon(level_triagle, color[chart_info.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = chart_info.title
            if self._coloum_width(title) > 12:
                title = self._change_column_width(title, 12) + "..."
            temp_draw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            temp_draw.text((7, 29), f"ID: {chart_info.song_id}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            temp_draw.text((96, 42), chart_info.rate, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            if chart_info.combo:
                temp_draw.text((80, 27), chart_info.combo, "white", font)
            if chart_info.sync:
                temp_draw.text((110, 27), chart_info.sync, "white", font)
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
                temp_draw.text(
                    (90, 61),
                    calc_dxstar(chart_info.dx_score, chart_info.dx_score_max),
                    "white",
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
            cover_path = os.path.join(mai_cover_path, f"{chart_info.song_id}.png")
            if not os.path.exists(cover_path):
                cover_path = os.path.join(mai_cover_path, "0.png")

            if os.path.exists(cover_path):
                temp = Image.open(cover_path).convert("RGB")
                temp = self._resize_image(temp, item_weight / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - item_height) / 2, item_weight, (temp.size[1] + item_height) / 2)
                )
                temp = temp.filter(ImageFilter.GaussianBlur(2))
                temp = temp.point(lambda p: int(p * 0.72))
            else:
                temp = Image.new("RGB", (int(item_weight), int(item_height)), (111, 111, 111, 255))

            temp_draw = ImageDraw.Draw(temp)
            temp_draw.polygon(level_triagle, color[chart_info.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = chart_info.title
            if self._coloum_width(title) > 12:
                title = self._change_column_width(title, 12) + "..."
            temp_draw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            temp_draw.text((7, 29), f"ID: {chart_info.song_id}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            temp_draw.text((6, 42), f"{chart_info.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            temp_draw.text((96, 42), chart_info.rate, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            if chart_info.combo:
                temp_draw.text((80, 27), chart_info.combo, "white", font)
            if chart_info.sync:
                temp_draw.text((110, 27), chart_info.sync, "white", font)
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
                temp_draw.text(
                    (90, 61),
                    calc_dxstar(chart_info.dx_score, chart_info.dx_score_max),
                    "white",
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

    @staticmethod
    def _coloum_width(arg_str: str):
        count = 0
        for str_ in arg_str:
            inside_code = ord(str_)
            if inside_code == 0x0020:
                count += 1
            elif inside_code < 0x7F:
                count += 1
            else:
                count += 2
        return count

    @staticmethod
    def _change_column_width(arg_str: str, arg_len: int):
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
            list_str.append(str_)
            if count == arg_len:
                return "".join(list_str)
        return "".join(list_str)

    def draw(self):
        img_draw = ImageDraw.Draw(self.img)
        font = ImageFont.truetype(noto_sans_demilight_path, 30, encoding="utf-8")
        img_draw.text((34, 24), " ".join(self.username), fill="black", font=font)
        font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
        img_draw.text(
            (34, 64), f"RATING    {self.player_rating}", fill="black", font=font
        )
        font = ImageFont.truetype(noto_sans_demilight_path, 20, encoding="utf-8")
        img_draw.text((34, 114), f"STANDARD ({self.sd_rating})", fill="black", font=font)
        img_draw.text((34, 914), f"NEW ({self.dx_rating})", fill="black", font=font)
        self._draw_best_list(self.img, self.sd_best, self.dx_best)

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        img_draw.text(
            (5, 1285), "Generated by Teahouse Studios \"AkariBot\"", "black", font=font
        )

    def get_dir(self):
        return self.img


async def generate(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Optional[Image.Image]:
    resp = await get_record(msg, payload, use_cache)
    sd_best = BestList(35)
    dx_best = BestList(15)
    dx: List[Dict] = resp["charts"]["dx"]
    sd: List[Dict] = resp["charts"]["sd"]
    for c in sd:
        sd_best.push(await ChartInfo.from_json(c))
    for c in dx:
        dx_best.push(await ChartInfo.from_json(c))
    pic = DrawBest(sd_best, dx_best, resp["nickname"]).get_dir()
    return pic
