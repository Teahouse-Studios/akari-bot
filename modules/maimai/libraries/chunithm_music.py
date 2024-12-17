import traceback
from copy import deepcopy
from typing import Dict, List, Optional, Union, Tuple, Any

import orjson as json

from core.logger import Logger
from core.utils.http import get_url
from core.utils.random import Random
from .chunithm_mapping import *


def cross(checker: List[Any], elem: Optional[Union[Any, List[Any]]], diff):
    ret = False
    diff_ret = []
    if not elem or elem is Ellipsis:
        return True, diff
    if isinstance(elem, List):
        for _j in range(len(checker)) if diff is Ellipsis else diff:
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if __e in elem:
                diff_ret.append(_j)
                ret = True
    elif isinstance(elem, Tuple):
        for _j in range(len(checker)) if diff is Ellipsis else diff:
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem[0] <= __e <= elem[1]:
                diff_ret.append(_j)
                ret = True
    else:
        for _j in range(len(checker)) if diff is Ellipsis else diff:
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem == __e:
                return True, [_j]
    return ret, diff_ret


def in_or_equal(checker: Any, elem: Optional[Union[Any, List[Any]]]):
    if elem is Ellipsis:
        return True
    if isinstance(elem, List):
        return checker in elem
    if isinstance(elem, Tuple):
        return elem[0] <= checker <= elem[1]
    return checker == elem


class Chart(Dict):
    combo: Optional[int] = None
    charter: Optional[int] = None

    def __getattribute__(self, item):
        if item == "combo":
            return self["combo"]
        if item == "charter":
            return self["charter"]
        return super().__getattribute__(item)


class Music(Dict):
    id: Optional[str] = None
    title: Optional[str] = None
    ds: Optional[List[float]] = None
    level: Optional[List[str]] = None
    genre: Optional[str] = None
    bpm: Optional[float] = None
    version: Optional[str] = None
    charts: Optional[Chart] = None
    artist: Optional[str] = None

    diff: List[int] = []

    def __getattribute__(self, item):
        if item in {"genre", "artist", "bpm", "version"}:
            if item == "version":
                return self["basic_info"]["from"]
            return self["basic_info"][item]
        if item in self:
            return self[item]
        return super().__getattribute__(item)


class MusicList(List[Music]):
    def by_id(self, music_id: str) -> Optional[Music]:
        for music in self:
            if music.id == int(music_id):
                return music
        return None

    def by_title(self, music_title: str) -> Optional[Music]:
        for music in self:
            if music.title.lower() == music_title.lower():
                return music
        return None

    def random(self):
        return Random.choice(self)

    def filter(
        self,
        *,
        level: Optional[Union[str, List[str]]] = ...,
        ds: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
        title: Optional[str] = ...,
        title_search: Optional[str] = ...,
        genre: Optional[Union[str, List[str]]] = ...,
        bpm: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
        diff: List[int] = ...,
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
            if not in_or_equal(music.bpm, bpm):
                continue
            if title is not Ellipsis and not in_or_equal(
                music.title.lower(), title.lower()
            ):
                continue
            if (
                title_search is not Ellipsis
                and title_search.lower() not in music.title.lower()
            ):
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
            Logger.error(traceback.format_exc())
            return False

    @staticmethod
    async def dl_cache():
        try:
            url = "https://www.diving-fish.com/api/chunithmprober/music_data"
            data = await get_url(url, 200, fmt="json")
            if data:
                with open(chu_song_info_path, "wb") as f:
                    f.write(json.dumps(data))
            return data
        except Exception:
            Logger.error(traceback.format_exc())
            try:
                with open(chu_song_info_path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                return data
            except Exception:
                return None
