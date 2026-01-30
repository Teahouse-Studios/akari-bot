from PIL import Image, ImageDraw, ImageFont

from core.builtins.bot import Bot
from core.builtins.message.internal import I18NContext
from core.constants.path import noto_sans_demilight_path
from .maimaidx_apidata import get_total_record
from .maimaidx_mapping import *
from .maimaidx_music import TotalList

total_list = TotalList()


class DrawLevelList:
    def __init__(
        self,
        level,
        goal,
        song_list,
        song_played
    ):
        self.level = level
        self.goal = goal
        self.song_list = song_list
        self.song_played = song_played
        self.image_size = 80
        self.spacing = 10
        self.margin = 20
        self.diff_colors = [
            (69, 193, 36),
            (255, 186, 1),
            (255, 90, 102),
            (134, 49, 200),
            (217, 197, 233),
        ]
        self.img = None
        self.create_ranked_image()

    def _get_goal_color(self):
        match self.goal:
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
            case _:
                color = (255, 255, 255)
        return color

    @staticmethod
    def _get_luminance(r, g, b):
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def create_ranked_image(self):
        total_width = 10 * (self.image_size + self.spacing) - self.spacing + 2 * self.margin

        total_height = self.margin
        for level, elements in self.song_list.items():
            if not elements:
                continue
            rows = (len(elements) + 9) // 10
            total_height += rows * (self.image_size + self.spacing + 20) + 40

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
            for _, i in enumerate(elements):
                sid = i[0]
                df = i[1]

                if x_offset + self.image_size > total_width - self.margin:
                    x_offset = self.margin
                    y_offset += self.image_size + self.spacing + 20

                cover_path = mai_cover_path / f"{sid}.png"
                if cover_path.exists():
                    cover = Image.open(cover_path)
                    cover = cover.resize((self.image_size, self.image_size))
                    self.img.paste(cover, (x_offset, y_offset))
                elif (mai_cover_path / "0.png").exists():
                    cover = Image.open(mai_cover_path / "0.png")
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
                dcolor = self.diff_colors[df]
                luminance = self._get_luminance(*dcolor)
                text_color = (0, 0, 0) if luminance > 140 else (255, 255, 255)

                # 左侧用于放置标记
                draw.rectangle(
                    [x_offset, bar_top, x_offset + large_bar_width, bar_top + bar_height],
                    fill=(0, 0, 0),
                )

                # 右侧用于放置封面ID
                draw.rectangle(
                    [x_offset + large_bar_width, bar_top, x_offset + self.image_size, bar_top + bar_height],
                    fill=dcolor,
                )

                # 绘制封面ID
                font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
                bbox = draw.textbbox((0, 0), str(sid), font=font)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                text_x = x_offset + large_bar_width + (small_bar_width - text_width) // 2
                text_y = bar_top + (bar_height - text_height) // 2
                draw.text((text_x, text_y), str(sid), fill=text_color, font=font)

                if self.goal:
                    if self.goal in rate_list:
                        rank_list = rate_list
                        mark_fill = [(69, 174, 255),
                                     (69, 174, 255),
                                     (69, 174, 255),
                                     (69, 174, 255),
                                     (69, 174, 255),
                                     (255, 129, 141),
                                     (255, 129, 141),
                                     (255, 129, 141),
                                     (239, 243, 13),
                                     (239, 243, 13),
                                     (239, 243, 13),
                                     (239, 243, 13),
                                     (239, 243, 13),
                                     (239, 243, 13)]
                    elif self.goal in combo_list:
                        rank_list = combo_list
                        mark_fill = [(129, 217, 85),
                                     (129, 217, 85),
                                     (249, 128, 4),
                                     (249, 128, 4)]
                    elif self.goal in sync_list:
                        rank_list = sync_list
                        mark_fill = [(49, 195, 246),
                                     (69, 174, 255),
                                     (69, 174, 255),
                                     (249, 128, 4),
                                     (249, 128, 4)]
                    else:
                        rank_list = []
                        mark_fill = []

                    rank = next((c for a, b, c in self.song_played if a == sid and b == df), None)
                    rank_index = rank_list.index(rank) + 1 if rank else 0

                    # 分段填充颜色
                    mark_width = large_bar_width / len(mark_fill)  # 使用浮点数计算
                    for i in range(rank_index):
                        draw.rectangle(
                            [
                                x_offset + i * mark_width,
                                bar_top,
                                x_offset + (i + 1) * mark_width if i < rank_index else x_offset + large_bar_width,
                                bar_top + bar_height,
                            ],
                            fill=mark_fill[i],
                        )

                    if rank_index >= rank_list.index(self.goal) + 1:
                        overlay = Image.new("RGBA", (self.image_size, self.image_size), (0, 0, 0, 180))
                        self.img.paste(overlay, (x_offset, y_offset), overlay)

                        text_color = self._get_goal_color()
                        font = ImageFont.truetype(noto_sans_demilight_path, 24, encoding="utf-8")

                        def get_text_size(text, font):
                            bbox = font.getbbox(text)
                            width = bbox[2] - bbox[0]
                            height = bbox[3] - bbox[1]
                            return width, height

                        text_width, text_height = get_text_size(self.goal, font)

                        text_x = x_offset
                        text_y = y_offset + (self.image_size - text_height) // 2

                        if self.goal in ["SSS", "SSS+"]:
                            char_sizes = [font.getbbox(c)[2] - font.getbbox(c)[0] for c in self.goal]
                            total_text_width = sum(char_sizes)
                            text_x = x_offset + (self.image_size - total_text_width) // 2
                            text_y = y_offset + (self.image_size - font.getbbox("A")[3]) // 2  # 大致高度居中

                            for i, char in enumerate(self.goal):
                                char_width, _ = get_text_size(char, font)
                                draw.text((text_x, text_y), char, fill=text_color[i], font=font)
                                text_x += char_width  # 更新x坐标，绘制下一个字母
                        else:
                            draw.text(
                                (x_offset + (self.image_size - text_width) // 2,
                                 y_offset + (self.image_size - text_height) // 2),
                                self.goal,
                                fill=text_color,
                                font=font
                            )

                x_offset += self.image_size + self.spacing

            y_offset += self.image_size + self.spacing + 20

        font = ImageFont.truetype(noto_sans_demilight_path, 10, encoding="utf-8")
        draw.text(
            (5, total_height - 15), "Generated by Teahouse Studios \"AkariBot\"", (0, 0, 0), font=font
        )

    def get_dir(self):
        return self.img


async def _get_level_process(msg: Bot.MessageSession,
                             payload: dict,
                             level: str,
                             goal: str | None = None,
                             use_cache: bool = True) -> tuple[dict[str, list[str]], list[tuple[str, int]]]:
    res = await get_total_record(msg, payload, use_cache)
    records: list = res["records"]

    song_played = []
    if goal:
        if goal in rate_list:
            for song in records:
                try:
                    rank = next(rank for interval, rank in score_to_rate.items()
                                if interval[0] <= song["achievements"] < interval[1])
                except StopIteration:
                    continue
                song_played.append((str(song["song_id"]), song["level_index"], rank))
        elif goal in combo_list:
            for song in records:
                rank = combo_mapping[song["fc"]] if song["fc"] else None
                song_played.append((str(song["song_id"]), song["level_index"], rank))
        elif goal in sync_list:
            for song in records:
                rank = sync_mapping[song["fs"]] if song["fs"] else None
                song_played.append((str(song["song_id"]), song["level_index"], rank))
        else:
            await msg.finish(I18NContext("maimai.message.goal_invalid"))

    song_list = {}

    for music in (await total_list.get()).filter(level=level):
        if int(music.id) < 100000:  # 过滤宴谱
            indices = [i for i, lv in enumerate(music.level) if lv == level]
            for idx in indices:
                const = str(music.ds[idx])
                if const not in song_list:
                    song_list[const] = []
                song_list[const].append((music.id, idx))

    song_list = {k: song_list[k] for k in sorted(song_list, reverse=True)}

    return song_list, song_played


async def generate(msg: Bot.MessageSession, payload: dict, level: str, goal: str | None, use_cache: bool = True) -> Image.Image | None:
    if goal:
        goal = goal.upper()
    song_list, song_played = await _get_level_process(msg, payload, level, goal, use_cache)

    pic = DrawLevelList(level, goal, song_list, song_played).get_dir()
    return pic
