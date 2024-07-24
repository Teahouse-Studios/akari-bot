import math
import os
import traceback
from typing import Optional, Dict, List, Tuple
import ujson as json
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from core.builtins import Bot
from .maimaidx_music import get_cover_len5_id, TotalList
from .maimaidx_apidata import get_record
from .maimaidx_utils import compute_rating, calc_dxstar

total_list = TotalList()

scoreRank = ['D', 'C', 'B', 'BB', 'BBB', 'A', 'AA', 'AAA', 'S', 'S+', 'SS', 'SS+', 'SSS', 'SSS+']
combo = ['', 'FC', 'FC+', 'AP', 'AP+']
sync = ['', 'SYNC', 'FS', 'FS+', 'FSD', 'FSD+']
diffs = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']


class ChartInfo(object):
    def __init__(self, idNum: str, diff: int, tp: str, ra: int, achievement: float, dxScore: int, dxScoreMax: int,
                 comboId: int, syncId: int, scoreId: int, title: str, ds: float, lv: str):
        self.idNum = idNum
        self.diff = diff
        self.tp = tp
        self.ra = compute_rating(ds, achievement),
        self.achievement = achievement
        self.dxScore = dxScore
        self.dxScoreMax = dxScoreMax
        self.comboId = comboId
        self.syncId = syncId
        self.scoreId = scoreId
        self.title = title
        self.ds = ds
        self.lv = lv

    def __str__(self):
        return '%-50s' % f'{self.title} [{self.tp}]' + f'{self.ds}\t{diffs[self.diff]}\t{self.ra}'

    def __eq__(self, other):
        return self.ra == other.ra

    def __lt__(self, other):
        return self.ra < other.ra

    @classmethod
    async def from_json(cls, data):
        rate = ['d', 'c', 'b', 'bb', 'bbb', 'a', 'aa', 'aaa', 's', 'sp', 'ss', 'ssp', 'sss', 'sssp']
        ri = rate.index(data["rate"])
        fc = ['', 'fc', 'fcp', 'ap', 'app']
        fi = fc.index(data["fc"])
        fs = ['', 'sync', 'fs', 'fsp', 'fsd', 'fsdp']
        si = fs.index(data["fs"])
        music = (await total_list.get()).by_id(str(data["song_id"]))
        dxscore_max = sum(music['charts'][data['level_index']]['notes']) * 3
        return cls(
            idNum=data["song_id"],
            title=data["title"],
            diff=data["level_index"],
            ds=data["ds"],
            ra=data["ra"],
            dxScore=data["dxScore"],
            dxScoreMax=dxscore_max,
            comboId=fi,
            syncId=si,
            scoreId=ri,
            lv=data["level"],
            achievement=data["achievements"],
            tp=data["type"]
        )


class BestList(object):

    def __init__(self, size: int):
        self.data = []
        self.size = size

    def push(self, elem: ChartInfo):
        if len(self.data) >= self.size and elem < self.data[-1]:
            return
        self.data.append(elem)
        self.data.sort()
        self.data.reverse()
        while (len(self.data) > self.size):
            del self.data[-1]

    def pop(self):
        del self.data[-1]

    def __str__(self):
        return '[\n\t' + ', \n\t'.join([str(ci) for ci in self.data]) + '\n]'

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index]


class DrawBest(object):

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
        self.cover_dir = os.path.abspath('./assets/maimai/static/mai/cover/')
        self.img = Image.new('RGBA', (860, 1300), color=(211, 211, 211, 255))  # 创建空白图像
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

    def _Q2B(self, uchar):
        """单个字符 全角转半角"""
        inside_code = ord(uchar)
        if inside_code == 0x3000:
            inside_code = 0x0020
        else:
            inside_code -= 0xfee0
        if inside_code < 0x0020 or inside_code > 0x7e:  # 转完之后不是半角字符返回原来的字符
            return uchar
        return chr(inside_code)

    def _resizePic(self, img, time):
        return img.resize((int(img.size[0] * time), int(img.size[1] * time)))

    def _drawBestList(self, img: Image.Image, sdBest: BestList, dxBest: BestList):
        itemW = 150
        itemH = 100
        Color = [(69, 193, 36), (255, 186, 1), (255, 90, 102), (134, 49, 200), (217, 197, 233)]
        levelTriagle = [(itemW, 0), (itemW - 27, 0), (itemW, 27)]
        imgDraw = ImageDraw.Draw(img)
        textFontPath = os.path.abspath('./assets/Noto Sans CJK DemiLight.otf')
        symbolFontPath = os.path.abspath('./assets/NotoSansSymbols2-Regular.ttf')

        for num in range(min(len(self.sdBest), 35)):
            i = num // 5
            j = num % 5
            chartInfo = sdBest[num]
            pngPath = os.path.join(self.cover_dir, f'{get_cover_len5_id(chartInfo.idNum)}.png')
            if not os.path.exists(pngPath):
                pngPath = os.path.join(self.cover_dir, '01000.png')
            temp = Image.open(pngPath).convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(2))
            temp = temp.point(lambda p: int(p * 0.72))

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(textFontPath, 18, encoding='utf-8')
            title = chartInfo.title
            if self._coloumWidth(title) > 12:
                title = self._changeColumnWidth(title, 12) + '...'
            tempDraw.text((6, 7), title, 'white', font)
            font = ImageFont.truetype(textFontPath, 10, encoding='utf-8')
            tempDraw.text((7, 29), f'ID: {chartInfo.idNum}', 'white', font)
            font = ImageFont.truetype(textFontPath, 16, encoding='utf-8')
            tempDraw.text((6, 42), f'{"%.4f" % chartInfo.achievement}%', 'white', font)
            font = ImageFont.truetype(textFontPath, 18, encoding='utf-8')
            tempDraw.text((96, 42), scoreRank[chartInfo.scoreId], 'white', font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            if chartInfo.comboId:
                tempDraw.text((80, 27), combo[chartInfo.comboId], 'white', font)
            if chartInfo.syncId:
                tempDraw.text((110, 27), sync[chartInfo.syncId], 'white', font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            tempDraw.text((7, 63), f'{chartInfo.dxScore}/{chartInfo.dxScoreMax}', 'white',
                          font)
            font = ImageFont.truetype(symbolFontPath, 12, encoding='utf-8')
            tempDraw.text((90, 61), calc_dxstar(chartInfo.dxScore, chartInfo.dxScoreMax), 'white',
                          font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            tempDraw.text((7, 80), f'{chartInfo.ds} -> {compute_rating(chartInfo.ds, chartInfo.achievement)}', 'white',
                          font)
            tempDraw.text((120, 80), f'#{num + 1}', 'white', font)

            recBase = Image.new('RGBA', (itemW, itemH), 'black')
            recBase = recBase.point(lambda p: int(p * 0.8))
            self.img.paste(recBase, (self.COLOUMS_IMG[j + 1] + 5, self.ROWS_IMG[i] + 5))
            self.img.paste(temp, (self.COLOUMS_IMG[j + 1] + 4, self.ROWS_IMG[i] + 4))

        for num in range(min(len(self.dxBest), 15)):
            i = num // 5
            j = num % 5
            chartInfo = dxBest[num]
            pngPath = os.path.join(self.cover_dir, f'{get_cover_len5_id(chartInfo.idNum)}.png')
            if not os.path.exists(pngPath):
                pngPath = os.path.join(self.cover_dir, '01000.png')
            temp = Image.open(pngPath).convert('RGB')
            temp = self._resizePic(temp, itemW / temp.size[0])
            temp = temp.crop((0, (temp.size[1] - itemH) / 2, itemW, (temp.size[1] + itemH) / 2))
            temp = temp.filter(ImageFilter.GaussianBlur(2))
            temp = temp.point(lambda p: int(p * 0.72))

            tempDraw = ImageDraw.Draw(temp)
            tempDraw.polygon(levelTriagle, Color[chartInfo.diff])
            font = ImageFont.truetype(textFontPath, 18, encoding='utf-8')
            title = chartInfo.title
            if self._coloumWidth(title) > 12:
                title = self._changeColumnWidth(title, 12) + '...'
            tempDraw.text((6, 7), title, 'white', font)
            font = ImageFont.truetype(textFontPath, 10, encoding='utf-8')
            tempDraw.text((7, 29), f'ID: {chartInfo.idNum}', 'white', font)
            font = ImageFont.truetype(textFontPath, 16, encoding='utf-8')
            tempDraw.text((6, 42), f'{"%.4f" % chartInfo.achievement}%', 'white', font)
            font = ImageFont.truetype(textFontPath, 18, encoding='utf-8')
            tempDraw.text((96, 42), scoreRank[chartInfo.scoreId], 'white', font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            if chartInfo.comboId:
                tempDraw.text((80, 27), combo[chartInfo.comboId], 'white', font)
            if chartInfo.syncId:
                tempDraw.text((110, 27), sync[chartInfo.syncId], 'white', font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            tempDraw.text((7, 63), f'{chartInfo.dxScore}/{chartInfo.dxScoreMax}', 'white',
                          font)
            font = ImageFont.truetype(symbolFontPath, 12, encoding='utf-8')
            tempDraw.text((90, 61), calc_dxstar(chartInfo.dxScore, chartInfo.dxScoreMax), 'white',
                          font)
            font = ImageFont.truetype(textFontPath, 12, encoding='utf-8')
            tempDraw.text((7, 80), f'{chartInfo.ds} -> {compute_rating(chartInfo.ds, chartInfo.achievement)}', 'white',
                          font)
            tempDraw.text((120, 80), f'#{num + 1}', 'white', font)

            recBase = Image.new('RGBA', (itemW, itemH), 'black')
            recBase = recBase.point(lambda p: int(p * 0.8))
            self.img.paste(recBase, (self.COLOUMS_IMG[j + 1] + 5, self.ROWS_IMG[i + 7] + 5))
            self.img.paste(temp, (self.COLOUMS_IMG[j + 1] + 4, self.ROWS_IMG[i + 7] + 4))

    def _coloumWidth(self, arg_str):
        count = 0
        for str_ in arg_str:
            inside_code = ord(str_)
            if inside_code == 0x0020:
                count += 1
            elif inside_code < 0x7f:
                count += 1
            else:
                count += 2
        return count

    def _changeColumnWidth(self, arg_str, arg_len):
        count = 0
        list_str = []
        for str_ in arg_str:
            inside_code = ord(str_)
            if inside_code == 0x0020:
                count += 1
            elif inside_code < 0x7f:
                count += 1
            else:
                count += 2
            list_str.append(str_)
            if count == arg_len:
                return "".join(list_str)
        return "".join(list_str)

    def draw(self):
        textFontPath = os.path.abspath('./assets/Noto Sans CJK DemiLight.otf')
        imgDraw = ImageDraw.Draw(self.img)
        font = ImageFont.truetype(textFontPath, 30, encoding='utf-8')
        imgDraw.text((34, 24), " ".join(self.userName), fill='black', font=font)
        font = ImageFont.truetype(textFontPath, 16, encoding='utf-8')
        imgDraw.text((34, 64), f"RATING    {self.playerRating}", fill='black', font=font)
        font = ImageFont.truetype(textFontPath, 20, encoding='utf-8')
        imgDraw.text((34, 114), f"STANDARD ({self.sdRating})", fill='black', font=font)
        imgDraw.text((34, 914), f"NEW ({self.dxRating})", fill='black', font=font)
        self._drawBestList(self.img, self.sdBest, self.dxBest)

        font = ImageFont.truetype(textFontPath, 10, encoding='utf-8')
        imgDraw.text((5, 1285), f'Generated by Teahouse Studios "Akaribot"', 'black', font=font)

    def getDir(self):
        return self.img


async def generate(msg: Bot.MessageSession, payload: dict, use_cache: bool = True) -> Tuple[Optional[Image.Image], bool]:
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
