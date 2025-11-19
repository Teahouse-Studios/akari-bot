from typing import Optional, Dict, List

from PIL import Image, ImageDraw, ImageFont

from core.builtins.bot import Bot
from core.constants.path import noto_sans_bold_path, noto_sans_demilight_path, noto_sans_symbol_path
from .chunithm_apidata import get_record
from .chunithm_mapping import (
    chu_cover_path,
    score_to_rate,
    combo_mapping,
    diff_list,
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
    def __init__(self, best_30: BestList, new_20: BestList, username: str):
        self.best_30 = best_30
        self.new_20 = new_20
        self.username = self._fullwidth_to_halfwidth(username)
        self.b30_rating = 0
        self.n20_rating = 0
        self.player_rating = 0
        self.b30_rating = sum(c.ra for c in best_30) / 30
        self.n20_rating = sum(c.ra for c in new_20) / 20
        self.player_rating = (sum(c.ra for c in best_30) + sum(c.ra for c in new_20)) / 50

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
    def _get_goal_color(goal: str):
        match goal:
            case "C" | "D":
                color = (206, 196, 204)
            case "B" | "BB" | "BBB":
                color = (69, 174, 255)
            case "A" | "AA" | "AAA":
                color = (239, 243, 13)
            case "S" | "S+" | "SS" | "SS+" | "SSS" | "SSS+":
                color = (173, 244, 248)
            case "FULL COMBO":
                color = (239, 243, 13)
            case "ALL JUSTICE":
                color = (173, 244, 248)
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
            title = chart_info.title
            if self._coloum_width(title) > 12:
                title = self._change_column_width(title, 12) + "..."
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
            title = chart_info.title
            if self._coloum_width(title) > 12:
                title = self._change_column_width(title, 12) + "..."
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
            (34, 64), f"RATING    {self.player_rating:.2f}", fill="black", font=font
        )
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


async def generate(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Optional[Image.Image]:
    resp = await get_record(msg, payload, use_cache)
    best = BestList(30)
    new = BestList(20)
    b30: List[Dict] = resp["records"]["b30"]
    n20: List[Dict] = resp["records"]["n20"]
    for c in b30:
        best.push(await ChartInfo.from_json(c))
    for c in n20:
        new.push(await ChartInfo.from_json(c))
    pic = DrawBest(best, new, resp["nickname"]).get_dir()
    return pic
