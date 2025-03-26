import os
from typing import Optional, Dict, List

from PIL import Image, ImageDraw, ImageFont

from core.builtins import Bot
from core.constants.path import noto_sans_demilight_path
from .maimaidx_apidata import get_plate
from .maimaidx_mapping import *
from .maimaidx_music import TotalList

total_list = TotalList()


class DrawPlateList:
    def __init__(
        self,
        plate,
        song_list,
        song_complete,
        remaster_required
    ):
        self.song_list = song_list
        self.song_complete = song_complete
        self.remaster_required = remaster_required
        self.version = plate[0]
        self.goal = plate[1:]
        if self.goal == "者":
            self.goal = "覇"
        elif self.goal == "舞舞":
            self.goal = "舞"
        self.image_size = 80
        self.spacing = 10
        self.margin = 20
        self.rank_colors = [
            (69, 193, 36),
            (255, 186, 1),
            (255, 90, 102),
            (134, 49, 200),
            (217, 197, 233),
        ]
        self.cover_marks = {}
        self.img = None
        self.update_cover_marks()
        self.create_ranked_image()

    def _get_version_color(self):
        match self.version:
            case "真":
                color = (89, 174, 229)
            case "超":
                color = (223, 254, 114)
            case "檄":
                color = (181, 230, 1)
            case "橙":
                color = (254, 208, 120)
            case "暁":
                color = (254, 120, 35)
            case "桃":
                color = (255, 10, 121)
            case "櫻":
                color = (254, 106, 158)
            case "紫":
                color = (185, 131, 255)
            case "菫":
                color = (116, 50, 220)
            case "白":
                color = (179, 235, 252)
            case "雪":
                color = (103, 254, 253)
            case "輝":
                color = (154, 160, 254)
            case "覇" | "舞":
                color = (221, 121, 237)
            case "熊" | "華":
                color = (239, 95, 95)
            case "爽" | "煌":
                color = (255, 255, 95)
            case "宙" | "星":
                color = (138, 200, 251)
            case "祭" | "祝":
                color = (184, 123, 191)
            case "双" | "宴":
                color = (255, 172, 62)
            case _:
                color = (0, 0, 0)
        return color

    def _get_goal_color(self):
        match self.goal:
            case "覇":
                color = (255, 129, 141)
            case "極":
                color = (129, 217, 85)
            case "将":
                color = (239, 243, 13)
            case "神":
                color = (252, 197, 49)
            case "舞":
                color = (69, 174, 255)
            case _:
                color = (255, 255, 255)
        return color

    @staticmethod
    def _get_luminance(r, g, b):
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def create_ranked_image(self):
        total_width = 10 * (self.image_size + self.spacing) - self.spacing + 2 * self.margin
        total_height = 0
        for level, elements in self.song_list.items():
            if not elements:
                continue
            rows = (len(elements) + 9) // 10
            total_height += rows * (self.image_size + self.spacing + 20) + 15

        total_height += (len(self.song_list) - 1) * self.spacing
        self.img = Image.new("RGB", (total_width, total_height), (211, 211, 211))
        draw = ImageDraw.Draw(self.img)

        y_offset = self.margin

        for level, elements in self.song_list.items():
            if not elements:
                continue

            font = ImageFont.truetype(noto_sans_demilight_path, 24, encoding="utf-8")
            draw.text((self.margin, y_offset), level, fill=(0, 0, 0), font=font)
            y_offset += 30

            x_offset = self.margin
            for _, sid in enumerate(elements):
                if x_offset + self.image_size > total_width - self.margin:
                    x_offset = self.margin
                    y_offset += self.image_size + self.spacing + 20

                cover_path = os.path.join(mai_cover_path, f"{sid}.png")
                if os.path.exists(cover_path):
                    cover = Image.open(cover_path)
                    cover = cover.resize((self.image_size, self.image_size))
                    self.img.paste(cover, (x_offset, y_offset))
                elif os.path.exists(os.path.join(mai_cover_path, "0.png")):
                    cover = Image.open(os.path.join(mai_cover_path, "0.png"))
                    cover = cover.resize((self.image_size, self.image_size))
                    self.img.paste(cover, (x_offset, y_offset))
                else:
                    draw.rectangle(
                        [x_offset, y_offset, x_offset + self.image_size, y_offset + self.image_size],
                        fill=(240, 240, 240),
                    )
                    font = ImageFont.truetype(noto_sans_demilight_path, 20, encoding="utf-8")
                    bbox = draw.textbbox((0, 0), str(sid), font=font)
                    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    text_x = x_offset + (self.image_size - text_width) // 2
                    text_y = y_offset + (self.image_size - text_height) // 2
                    draw.text((text_x, text_y), str(sid), fill=(100, 100, 100), font=font)

                # 绘制灰色长方形
                bar_top = y_offset + self.image_size
                bar_height = 15
                large_bar_width = self.image_size * 0.6  # 左边部分的宽度，占比大
                small_bar_width = self.image_size * 0.4  # 右边部分的宽度，占比小
                vcolor = self._get_version_color()
                luminance = self._get_luminance(*vcolor)
                text_color = (0, 0, 0) if luminance > 140 else (255, 255, 255)

                # 左侧用于放置标记
                draw.rectangle(
                    [x_offset, bar_top, x_offset + large_bar_width, bar_top + bar_height],
                    fill=(0, 0, 0),
                )

                # 右侧用于放置封面ID
                draw.rectangle(
                    [x_offset + large_bar_width, bar_top, x_offset + self.image_size, bar_top + bar_height],
                    fill=vcolor,
                )

                if int(sid) in self.remaster_required:
                    mark_count = 5
                else:
                    mark_count = 4

                # 分段填充颜色
                mark_width = large_bar_width / mark_count  # 使用浮点数计算
                if sid not in self.cover_marks:
                    self.cover_marks[sid] = [False] * mark_count

                for i in range(mark_count):
                    if self.cover_marks[sid][i]:
                        draw.rectangle(
                            [
                                x_offset + i * mark_width,
                                bar_top,
                                x_offset + (i + 1) * mark_width if i < mark_count - 1 else x_offset + large_bar_width,
                                bar_top + bar_height,
                            ],
                            fill=self.rank_colors[i],
                        )

                # 绘制封面ID
                font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
                bbox = draw.textbbox((0, 0), str(sid), font=font)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                text_x = x_offset + large_bar_width + (small_bar_width - text_width) // 2
                text_y = bar_top + (bar_height - text_height) // 2
                draw.text((text_x, text_y), str(sid), fill=text_color, font=font)

                if all(self.cover_marks[sid]):
                    overlay = Image.new("RGBA", (self.image_size, self.image_size), (0, 0, 0, 180))  # 半透明黑色
                    self.img.paste(overlay, (x_offset, y_offset), overlay)  # 使用overlay进行粘贴

                    text_color = self._get_goal_color()
                    font = ImageFont.truetype(noto_sans_demilight_path, 36, encoding="utf-8")
                    bbox = draw.textbbox((0, 0), self.goal, font=font)
                    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    text_x = x_offset + (self.image_size - text_width) // 2
                    text_y = y_offset + (self.image_size - text_height) // 2
                    draw.text((text_x, text_y), self.goal, fill=text_color, font=font)

                x_offset += self.image_size + self.spacing

            y_offset += self.image_size + self.spacing + 20

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        draw.text(
            (5, total_height - 15), "Generated by Teahouse Studios \"AkariBot\"", (0, 0, 0), font=font
        )

    def update_cover_marks(self):
        for cover_id, diff in self.song_complete:
            for _, elements in self.song_list.items():
                if str(cover_id) in elements:
                    if str(cover_id) not in self.cover_marks:
                        if int(cover_id) in self.remaster_required:
                            self.cover_marks[str(cover_id)] = [False, False, False, False, False]
                        else:
                            self.cover_marks[str(cover_id)] = [False, False, False, False]
                    try:
                        self.cover_marks[str(cover_id)][diff] = True
                    except IndexError:
                        pass

    def get_dir(self):
        return self.img


async def get_plate_process(msg: Bot.MessageSession, payload: dict, plate: str, use_cache: bool = True) -> tuple[Dict[str, List[str]], List[tuple[str, int]]]:
    song_complete_basic = []
    song_complete_advanced = []
    song_complete_expert = []
    song_complete_master = []
    song_complete_remaster = []

    version = plate[0]
    goal = plate[1:]

    if version == "真":  # 真代为无印版本
        payload["version"] = ["maimai", "maimai PLUS"]
    elif version in ["覇", "舞"]:  # 霸者和舞牌需要全版本
        payload["version"] = list(set(list(sd_plate_mapping.values())))
    elif version in plate_mapping and version != "初":  # “初”不是版本名称
        payload["version"] = [plate_mapping[version]]
    else:
        await msg.finish(msg.locale.t("maimai.message.plate.plate_not_found"))

    res = await get_plate(msg, payload, version, use_cache)
    verlist = res["verlist"]

    if goal in ["将", "者"]:
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["achievements"] >= (100.0 if goal == "将" else 80.0):
                song_complete_basic.append((song["id"], song["level_index"]))
            if song["level_index"] == 1 and song["achievements"] >= (100.0 if goal == "将" else 80.0):
                song_complete_advanced.append((song["id"], song["level_index"]))
            if song["level_index"] == 2 and song["achievements"] >= (100.0 if goal == "将" else 80.0):
                song_complete_expert.append((song["id"], song["level_index"]))
            if song["level_index"] == 3 and song["achievements"] >= (100.0 if goal == "将" else 80.0):
                song_complete_master.append((song["id"], song["level_index"]))
            if version in ["覇", "舞"] and int(song["id"]) in mai_plate_remaster_required and \
               song["level_index"] == 4 and song["achievements"] >= (100.0 if goal == "将" else 80.0):
                song_complete_remaster.append((song["id"], song["level_index"]))  # 霸者和舞牌需要Re:MASTER难度
    elif goal == "極":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["fc"]:
                song_complete_basic.append((song["id"], song["level_index"]))
            if song["level_index"] == 1 and song["fc"]:
                song_complete_advanced.append((song["id"], song["level_index"]))
            if song["level_index"] == 2 and song["fc"]:
                song_complete_expert.append((song["id"], song["level_index"]))
            if song["level_index"] == 3 and song["fc"]:
                song_complete_master.append((song["id"], song["level_index"]))
            if version == "舞" and int(song["id"]) in mai_plate_remaster_required and \
                    song["level_index"] == 4 and song["fc"]:
                song_complete_remaster.append((song["id"], song["level_index"]))
    elif goal == "舞舞":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["fs"] in ["fsd", "fsdp"]:
                song_complete_basic.append((song["id"], song["level_index"]))
            if song["level_index"] == 1 and song["fs"] in ["fsd", "fsdp"]:
                song_complete_advanced.append((song["id"], song["level_index"]))
            if song["level_index"] == 2 and song["fs"] in ["fsd", "fsdp"]:
                song_complete_expert.append((song["id"], song["level_index"]))
            if song["level_index"] == 3 and song["fs"] in ["fsd", "fsdp"]:
                song_complete_master.append((song["id"], song["level_index"]))
            if version == "舞" and int(song["id"]) in mai_plate_remaster_required and \
               song["level_index"] == 4 and song["fs"] in ["fsd", "fsdp"]:
                song_complete_remaster.append((song["id"], song["level_index"]))
    elif goal == "神":
        for song in verlist:  # 将剩余歌曲ID和难度加入目标列表
            if song["level_index"] == 0 and song["fc"] in ["ap", "app"]:
                song_complete_basic.append((song["id"], song["level_index"]))
            if song["level_index"] == 1 and song["fc"] in ["ap", "app"]:
                song_complete_advanced.append((song["id"], song["level_index"]))
            if song["level_index"] == 2 and song["fc"] in ["ap", "app"]:
                song_complete_expert.append((song["id"], song["level_index"]))
            if song["level_index"] == 3 and song["fc"] in ["ap", "app"]:
                song_complete_master.append((song["id"], song["level_index"]))
            if version == "舞" and int(song["id"]) in mai_plate_remaster_required and \
               song["level_index"] == 4 and song["fc"] in ["ap", "app"]:
                song_complete_remaster.append((song["id"], song["level_index"]))
    else:
        await msg.finish(msg.locale.t("maimai.message.plate.plate_not_found"))

    song_expect = mai_plate_song_expect(version)
    song_list = {
        "15": [],
        "14+": [],
        "14": [],
        "13+": [],
        "13": [],
        "12+": [],
        "12": [],
        "11+": [],
        "11": [],
        "10+": [],
        "10": [],
        "9+": [],
        "9": [],
        "8+": [],
        "8": [],
        "7+": [],
        "7": [],
        "6": [],
        "5": [],
        "4": [],
        "3": [],
        "2": [],
        "1": [],
    }
    for music in (await total_list.get()):  # 将未游玩歌曲ID加入目标列表
        if music["basic_info"]["from"] in payload["version"] and int(
                music.id) not in song_expect and int(music.id) < 100000:  # 过滤宴谱
            levels = music.level if version in ["覇", "舞"] and int(
                music.id) in mai_plate_remaster_required else music.level[:4]
            sorted_levels = sorted(levels, key=lambda x: (
                int(x[:-1]) if x[-1] == "+" else int(x), x[-1] == "+"), reverse=True)
            song_list[sorted_levels[0]].append(music.id)

    song_complete_basic = [music for music in song_complete_basic if music[0] not in song_expect]
    song_complete_advanced = [music for music in song_complete_advanced if music[0] not in song_expect]
    song_complete_expert = [music for music in song_complete_expert if music[0] not in song_expect]
    song_complete_master = [music for music in song_complete_master if music[0] not in song_expect]
    song_complete_remaster = [music for music in song_complete_remaster if music[0] not in song_expect]
    song_complete: List[tuple[str, int]] = song_complete_basic + song_complete_advanced + \
        song_complete_expert + song_complete_master + song_complete_remaster

    return song_list, song_complete


async def generate(msg: Bot.MessageSession, payload: dict, plate: str, use_cache: bool = True) -> Optional[Image.Image]:
    version = plate[0]
    goal = plate[1:]

    if version in plate_version_ts_mapping:
        version = plate_version_ts_mapping[version]
    if goal in plate_goal_ts_mapping:
        goal = plate_goal_ts_mapping[goal]
    plate = version + goal

    song_list, song_complete = await get_plate_process(msg, payload, plate, use_cache)
    remaster_required = mai_plate_remaster_required if version in ["覇", "舞"] else []

    pic = DrawPlateList(plate, song_list, song_complete, remaster_required).get_dir()
    return pic
