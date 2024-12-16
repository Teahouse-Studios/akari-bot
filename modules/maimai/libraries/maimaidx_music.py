import traceback
from copy import deepcopy
from typing import Dict, List, Optional, Union, Tuple, Any

import orjson as json

from core.logger import Logger
from core.utils.http import get_url
from core.utils.random import Random
from .maimaidx_mapping import *


def get_cover_len5_id(mid: Union[int, str]) -> str:
    mid = int(mid)
    if 10000 < mid <= 11000:
        mid -= 10000
    return f'{mid:05d}'


def cross(checker: List[Any], elem: Optional[Union[Any, List[Any]]], diff):
    ret = False
    diff_ret = []
    if not elem or elem is Ellipsis:
        return True, diff
    if isinstance(elem, List):
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if __e in elem:
                diff_ret.append(_j)
                ret = True
    elif isinstance(elem, Tuple):
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem[0] <= __e <= elem[1]:
                diff_ret.append(_j)
                ret = True
    else:
        for _j in (range(len(checker)) if diff is Ellipsis else diff):
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
    elif isinstance(elem, Tuple):
        return elem[0] <= checker <= elem[1]
    else:
        return checker == elem


class Chart(Dict):
    tap: Optional[int] = None
    slide: Optional[int] = None
    hold: Optional[int] = None
    touch: Optional[int] = None
    brk: Optional[int] = None
    charter: Optional[int] = None
    dxscore: Optional[int] = None

    def __getattribute__(self, item):
        if item == 'tap':
            return self['notes'][0]
        elif item == 'hold':
            return self['notes'][1]
        elif item == 'slide':
            return self['notes'][2]
        elif item == 'touch':
            return self['notes'][3] if len(self['notes']) == 5 else 0
        elif item == 'brk':
            return self['notes'][-1]
        elif item == 'dxscore':
            return sum(self['charter']) * 3
        elif item == 'charter':
            return self['charter']
        return super().__getattribute__(item)


class Music(Dict):
    id: Optional[str] = None
    title: Optional[str] = None
    ds: Optional[List[float]] = None
    level: Optional[List[str]] = None
    genre: Optional[str] = None
    type: Optional[str] = None
    bpm: Optional[float] = None
    version: Optional[str] = None
    charts: Optional[Chart] = None
    release_date: Optional[str] = None
    artist: Optional[str] = None
    is_new: Optional[bool] = False
    diff: List[int] = []

    def __getattribute__(self, item):
        if item in {'genre', 'artist', 'release_date', 'bpm', 'version', 'is_new'}:
            if item == 'version':
                return self['basic_info']['from']
            return self['basic_info'][item]
        elif item in self:
            return self[item]
        return super().__getattribute__(item)


class MusicList(List[Music]):
    def by_id(self, music_id: str) -> Optional[Music]:
        for music in self:
            if music.id == music_id:
                return music
        return None

    def by_title(self, music_title: str) -> Optional[Music]:
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

    def filter(self,
               *,
               level: Optional[Union[str, List[str]]] = ...,
               ds: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
               title: Optional[str] = ...,
               title_search: Optional[str] = ...,
               genre: Optional[Union[str, List[str]]] = ...,
               bpm: Optional[Union[float, List[float], Tuple[float, float]]] = ...,
               dxtype: Optional[Union[str, List[str]]] = ...,
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
            if not in_or_equal(music.type, dxtype):
                continue
            if not in_or_equal(music.bpm, bpm):
                continue
            if title is not Ellipsis and not in_or_equal(music.title.lower(), title.lower()):
                continue
            if title_search is not Ellipsis and title_search.lower() not in music.title.lower():
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
            url = "https://www.diving-fish.com/api/maimaidxprober/music_data"
            data = await get_url(url, 200, fmt='json')
            if data:
                with open(mai_song_info_path, 'wb') as f:
                    f.write(json.dumps(data))
            return data
        except Exception:
            Logger.error(traceback.format_exc())
            try:
                with open(mai_song_info_path, 'r', encoding='utf-8') as f:
                    data = json.loads(f.read())
                return data
            except Exception:
                return None
