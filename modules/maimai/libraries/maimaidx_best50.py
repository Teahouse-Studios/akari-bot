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
        idNum: str,
        diff: int,
        tp: str,
        ra: int,
        achievement: float,
        dxScore: int,
        dxScoreMax: int,
        combo: int,
        sync: int,
        rate: int,
        title: str,
        ds: float,
        lv: str,
    ):
        self.idNum = idNum
        self.diff = diff
        self.tp = tp
        self.ra = compute_rating(ds, achievement)
        self.achievement = achievement
        self.dxScore = dxScore
        self.dxScoreMax = dxScoreMax
        self.combo = combo
        self.sync = sync
        self.rate = rate
        self.title = title
        self.ds = ds
        self.lv = lv

    def __str__(self):
        return f"{self.title:<50} [{self.tp}]{self.ds}\t{diff_list[self.diff]}\t{self.ra}"

    def __eq__(self, other):
        return self.ra == other.ra

    def __lt__(self, other):
        return self.ra < other.ra

    def __hash__(self):
        return hash(self.ra)

    @classmethod
    async def from_json(cls, data):
        music = (await total_list.get()).by_id(str(data["song_id"]))
        dxscore_max = sum(music["charts"][data["level_index"]]["notes"]) * 3
        return cls(
            idNum=data["song_id"],
            title=data["title"],
            diff=data["level_index"],
            ds=data["ds"],
            ra=data["ra"],
            dxScore=data["dxScore"],
            dxScoreMax=dxscore_max,
            combo=combo_mapping.get(data["fc"], ""),
            sync=sync_mapping.get(data["fs"], ""),
            rate=rate_mapping.get(data["rate"], ""),
            lv=data["level"],
            achievement=data["achievements"],
            tp=data["type"],
        )


class BestList:

    def __init__(self, size: int):
        self.data = []
        self.size = size

    def push(self, elem: ChartInfo):
        if len(self.data) >= self.size and elem < self.data[-1]:
            return
        self.data.append(elem)
        self.data.sort()
        self.data.reverse()
        while len(self.data) > self.size:
            del self.data[-1]

    def pop(self):
        del self.data[-1]

    def __str__(self):
        return "[\n\t" + ", \n\t".join([str(ci) for ci in self.data]) + "\n]"

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]


class DrawBest:

    def __init__(self, sdBest: List[ChartInfo], dxBest: List[ChartInfo], userName: str):
        self.sdBest = sdBest
        self.dxBest = dxBest
        self.userName = self._stringQ2B(userName)
        self.sdRating = 0
        self.dxRating = 0
        for sd in sdBest:
            self.sdRating += compute_rating(sd.ds, sd.achievement)
        for dx in dxBest:
            self.dxRating += compute_rating(dx.ds, dx.achievement)
        self.playerRating = self.sdRating + self.dxRating
        self.img = Image.new(
            "RGBA", (860, 1300), color=(211, 211, 211, 255)
        )  # 创建空白图像
        self.ROWS_IMG = []
        for i in range(7):
            self.ROWS_IMG.append(140 + 110 * i)
        for i in range(3):
            self.ROWS_IMG.append(940 + 110 * i)
        self.COLOUMS_IMG = [30]
        for i in range(5):
            self.COLOUMS_IMG.append(30 + 160 * i)
        self.draw()

    def _stringQ2B(self, ustring):
        """把字符串全角转半角"""
        return "".join([self._Q2B(uchar) for uchar in ustring])

    @staticmethod
    def _Q2B(uchar):
        """单个字符 全角转半角"""
        inside_code = ord(uchar)
        if inside_code == 0x3000:
            inside_code = 0x0020
        else:
            inside_code -= 0xFEE0
        if (
            inside_code < 0x0020 or inside_code > 0x7E
        ):  # 转完之后不是半角字符返回原来的字符
            return uchar
        return chr(inside_code)

    @staticmethod
    def _resizePic(img, time):
        return img.resize((int(img.size[0] * time), int(img.size[1] * time)))

    def _drawBestList(self, img: Image.Image, sdBest: BestList, dxBest: BestList):
        itemW = 150
        itemH = 100
        Color = [
            (69, 193, 36),
            (255, 186, 1),
            (255, 90, 102),
            (134, 49, 200),
            (217, 197, 233),
        ]
        levelTriagle = [(itemW, 0), (itemW - 27, 0), (itemW, 27)]
        ImageDraw.Draw(img)

        for num in range(min(len(self.sdBest), 35)):
            i = num // 5
            j = num % 5
            chartInfo = sdBest[num]
            pngPath = os.path.join(mai_cover_path, f"{chartInfo.idNum}.png")
            if not os.path.exists(pngPath):
                pngPath = os.path.join(mai_cover_path, "0.png")

            if os.path.exists(pngPath):
                temp = Image.open(pngPath).convert("RGB")
                temp = self._resizePic(temp, itemW / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2)
                )
                temp = temp.filter(ImageFilter.GaussianBlur(2))
                temp = temp.point(lambda p: int(p * 0.72))
            else:
                temp = Image.new("RGB", (int(itemW), int(itemH)), (111, 111, 111, 255))

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = chartInfo.title
            if self._coloumWidth(title) > 12:
                title = self._changeColumnWidth(title, 12) + "..."
            tempDraw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            tempDraw.text((7, 29), f"ID: {chartInfo.idNum}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            tempDraw.text((6, 42), f"{chartInfo.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            tempDraw.text((96, 42), chartInfo.rate, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            if chartInfo.combo:
                tempDraw.text((80, 27), chartInfo.combo, "white", font)
            if chartInfo.sync:
                tempDraw.text((110, 27), chartInfo.sync, "white", font)
            if chartInfo.dxScore:
                font = ImageFont.truetype(
                    noto_sans_demilight_path, 12, encoding="utf-8"
                )
                tempDraw.text(
                    (7, 63),
                    f"{chartInfo.dxScore}/{chartInfo.dxScoreMax}",
                    "white",
                    font,
                )
                font = ImageFont.truetype(noto_sans_symbol_path, 12, encoding="utf-8")
                tempDraw.text(
                    (90, 61),
                    calc_dxstar(chartInfo.dxScore, chartInfo.dxScoreMax),
                    "white",
                    font,
                )
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            tempDraw.text(
                (7, 80),
                f"{chartInfo.ds} -> {compute_rating(chartInfo.ds, chartInfo.achievement)}",
                "white",
                font,
            )
            tempDraw.text((120, 80), f"#{num + 1}", "white", font)

            recBase = Image.new("RGBA", (itemW, itemH), "black")
            recBase = recBase.point(lambda p: int(p * 0.8))
            self.img.paste(recBase, (self.COLOUMS_IMG[j + 1] + 5, self.ROWS_IMG[i] + 5))
            self.img.paste(temp, (self.COLOUMS_IMG[j + 1] + 4, self.ROWS_IMG[i] + 4))

        for num in range(min(len(self.dxBest), 15)):
            i = num // 5
            j = num % 5
            chartInfo = dxBest[num]
            pngPath = os.path.join(mai_cover_path, f"{chartInfo.idNum}.png")
            if not os.path.exists(pngPath):
                pngPath = os.path.join(mai_cover_path, "0.png")

            if os.path.exists(pngPath):
                temp = Image.open(pngPath).convert("RGB")
                temp = self._resizePic(temp, itemW / temp.size[0])
                temp = temp.crop(
                    (0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2)
                )
                temp = temp.filter(ImageFilter.GaussianBlur(2))
                temp = temp.point(lambda p: int(p * 0.72))
            else:
                temp = Image.new("RGB", (int(itemW), int(itemH)), (111, 111, 111, 255))

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            title = chartInfo.title
            if self._coloumWidth(title) > 12:
                title = self._changeColumnWidth(title, 12) + "..."
            tempDraw.text((6, 7), title, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
            tempDraw.text((7, 29), f"ID: {chartInfo.idNum}", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
            tempDraw.text((6, 42), f"{chartInfo.achievement:.4f}%", "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 18, encoding="utf-8")
            tempDraw.text((96, 42), chartInfo.rate, "white", font)
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            if chartInfo.combo:
                tempDraw.text((80, 27), chartInfo.combo, "white", font)
            if chartInfo.sync:
                tempDraw.text((110, 27), chartInfo.sync, "white", font)
            if chartInfo.dxScore:
                font = ImageFont.truetype(
                    noto_sans_demilight_path, 12, encoding="utf-8"
                )
                tempDraw.text(
                    (7, 63),
                    f"{chartInfo.dxScore}/{chartInfo.dxScoreMax}",
                    "white",
                    font,
                )
                font = ImageFont.truetype(noto_sans_symbol_path, 12, encoding="utf-8")
                tempDraw.text(
                    (90, 61),
                    calc_dxstar(chartInfo.dxScore, chartInfo.dxScoreMax),
                    "white",
                    font,
                )
            font = ImageFont.truetype(noto_sans_demilight_path, 12, encoding="utf-8")
            tempDraw.text(
                (7, 80),
                f"{chartInfo.ds} -> {compute_rating(chartInfo.ds, chartInfo.achievement)}",
                "white",
                font,
            )
            tempDraw.text((120, 80), f"#{num + 1}", "white", font)

            recBase = Image.new("RGBA", (itemW, itemH), "black")
            recBase = recBase.point(lambda p: int(p * 0.8))
            self.img.paste(
                recBase, (self.COLOUMS_IMG[j + 1] + 5, self.ROWS_IMG[i + 7] + 5)
            )
            self.img.paste(
                temp, (self.COLOUMS_IMG[j + 1] + 4, self.ROWS_IMG[i + 7] + 4)
            )

    @staticmethod
    def _coloumWidth(arg_str):
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
    def _changeColumnWidth(arg_str, arg_len):
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
        imgDraw = ImageDraw.Draw(self.img)
        font = ImageFont.truetype(noto_sans_demilight_path, 30, encoding="utf-8")
        imgDraw.text((34, 24), " ".join(self.userName), fill="black", font=font)
        font = ImageFont.truetype(noto_sans_demilight_path, 16, encoding="utf-8")
        imgDraw.text(
            (34, 64), f"RATING    {self.playerRating}", fill="black", font=font
        )
        font = ImageFont.truetype(noto_sans_demilight_path, 20, encoding="utf-8")
        imgDraw.text((34, 114), f"STANDARD ({self.sdRating})", fill="black", font=font)
        imgDraw.text((34, 914), f"NEW ({self.dxRating})", fill="black", font=font)
        self._drawBestList(self.img, self.sdBest, self.dxBest)

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        imgDraw.text(
            (5, 1285), "Generated by Teahouse Studios \"AkariBot\"", "black", font=font
        )

    def getDir(self):
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
    pic = DrawBest(sd_best, dx_best, resp["nickname"]).getDir()
    return pic
