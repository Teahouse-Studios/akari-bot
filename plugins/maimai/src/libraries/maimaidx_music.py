from copy import deepcopy
from typing import Any

import orjson

from core.logger import Logger
from core.utils.http import get_url
from core.utils.random import Random
from .maimaidx_mapping import *


def get_cover_len5_id(mid: int | str) -> str:
    mid = int(mid)
    if 10000 < mid <= 11000:
        mid -= 10000
    return f"{mid:05d}"


def cross(checker: list[Any], elem: Any | list[Any] | None, diff):
    ret = False
    diff_ret = []
    if not elem:
        return True, diff
    if isinstance(elem, list):
        for _j in enumerate(checker):
            __j = _j[0]
            if __j >= len(checker):
                continue
            __e = checker[__j]
            if __e in elem:
                diff_ret.append(__j)
                ret = True
    elif isinstance(elem, tuple):
        for _j in enumerate(checker):
            __j = _j[0]
            if __j >= len(checker):
                continue
            __e = checker[__j]
            if elem[0] <= __e <= elem[1]:
                diff_ret.append(__j)
                ret = True
    else:
        for _j in enumerate(checker):
            __j = _j[0]
            if __j >= len(checker):
                continue
            __e = checker[__j]
            if elem == __e:
                return True, [__j]
    return ret, diff_ret


def in_or_equal(checker: Any, elem: Any | list[Any] | None):
    if not elem:
        return True
    if isinstance(elem, list):
        return checker in elem
    if isinstance(elem, tuple):
        return elem[0] <= checker <= elem[1]
    return checker == elem


class Chart(dict):
    tap: int | None = None
    slide: int | None = None
    hold: int | None = None
    touch: int | None = None
    brk: int | None = None
    charter: int | None = None
    dxscore: int | None = None

    def __getattribute__(self, item):
        if item == "tap":
            return self["notes"][0]
        if item == "hold":
            return self["notes"][1]
        if item == "slide":
            return self["notes"][2]
        if item == "touch":
            return self["notes"][3] if len(self["notes"]) == 5 else 0
        if item == "brk":
            return self["notes"][-1]
        if item == "dxscore":
            return sum(self["charter"]) * 3
        if item == "charter":
            return self["charter"]
        return super().__getattribute__(item)


class Music(dict):
    id: str | None = None
    title: str | None = None
    ds: list[float] | None = None
    level: list[str] | None = None
    genre: str | None = None
    type: str | None = None
    bpm: float | None = None
    version: str | None = None
    charts: Chart | None = None
    release_date: str | None = None
    artist: str | None = None
    is_new: bool | None = False
    diff: list[int] = []

    def __getattribute__(self, item):
        if item in {"genre", "artist", "release_date", "bpm", "version", "is_new"}:
            if item == "version":
                return self["basic_info"]["from"]
            return self["basic_info"][item]
        if item in self:
            return self[item]
        return super().__getattribute__(item)


class MusicList(list[Music]):
    def by_id(self, music_id: str) -> Music | None:
        for music in self:
            if music.id == music_id:
                return music
        return None

    def by_title(self, music_title: str) -> Music | None:
        for music in self:
            if music.title.lower() == music_title.lower():
                return music
        return None

    def new(self):
        new_list = MusicList()
        for music in self:
            music = deepcopy(music)
            if not music.is_new:
                continue
            new_list.append(music)
        return new_list

    def random(self):
        return Random.choice(self)

    def filter(
        self,
        *,
        level: str | list[str] | None = None,
        ds: float | list[float] | tuple[float, float] | None = None,
        title: str | None = None,
        title_search: str | None = None,
        genre: str | list[str] | None = None,
        bpm: float | list[float] | tuple[float, float] | None = None,
        dxtype: str | list[str] | None = None,
        diff: list[int] = None,
    ):
        new_list = MusicList()
        for music in self:
            diff2 = diff
            music = deepcopy(music)
            ret, diff2 = cross(music.level, level, diff2)
            if not ret:
                continue
            ret, diff2 = cross(music.ds, ds, diff2)
            if not ret:
                continue
            if not in_or_equal(music.genre, genre):
                continue
            if not in_or_equal(music.type, dxtype):
                continue
            if not in_or_equal(music.bpm, bpm):
                continue
            if title and not in_or_equal(music.title.lower(), title.lower()):
                continue
            if title_search and title_search.lower() not in music.title.lower():
                continue
            music.diff = diff2
            new_list.append(music)
        return new_list


class TotalList:
    def __init__(self):
        self.total_list = None

    async def get(self):
        if not self.total_list:
            await self.update()
        return self.total_list

    async def update(self):
        try:
            obj = await self.dl_cache()
            total_list: MusicList = MusicList(obj)
            for __i in range(len(total_list)):
                total_list[__i] = Music(total_list[__i])
                for __j in range(len(total_list[__i].charts)):
                    total_list[__i].charts[__j] = Chart(total_list[__i].charts[__j])
            self.total_list = total_list
            return True
        except Exception:
            Logger.exception()
            return False

    @staticmethod
    async def dl_cache():
        try:
            url = "https://www.diving-fish.com/api/maimaidxprober/music_data"
            data = await get_url(url, 200, fmt="json")
            if data:
                with open(mai_song_info_path, "wb") as f:
                    f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
            return data
        except Exception:
            Logger.exception()
            try:
                with open(mai_song_info_path, "rb") as f:
                    data = orjson.loads(f.read())
                return data
            except Exception:
                return None
