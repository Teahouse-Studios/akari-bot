from copy import deepcopy
from typing import Any

import orjson

from core.logger import Logger
from core.utils.http import get_url
from core.utils.random import Random
from .chunithm_mapping import *


def process_lxns_to_diving_fish(data):
    version_map = {v["version"]: v["title"] for v in data.get("versions", [])}

    result = []
    for song in data.get("songs", []):
        basic_info = {
            "artist": song["artist"],
            "bpm": song["bpm"],
            "from": version_map.get(song["version"], "Unknown"),
            "genre": song["genre"],
            "title": song["title"]
        }

        charts = []
        ds = []
        levels = []

        for diff in song.get("difficulties", []):
            notes_ordered = [
                diff["notes"].get("tap", 0),
                diff["notes"].get("hold", 0),
                diff["notes"].get("slide", 0),
                diff["notes"].get("air", 0),
                diff["notes"].get("flick", 0)
            ]

            charter_name = diff.get("note_designer", "")
            charts.append({
                "charter": charter_name,
                "notes": notes_ordered
            })

            ds.append(diff.get("star", float(diff.get("level_value", 0.0))))
            levels.append(diff.get("kanji", diff.get("level", "")))

        title_with_kanji = song["title"]
        kanji_list = [diff.get("kanji") for diff in song.get("difficulties", []) if "kanji" in diff]
        if kanji_list:
            title_with_kanji = f"[{kanji_list[0]}]{song["title"]}"
            basic_info["title"] = title_with_kanji

        song_entry = {
            "basic_info": basic_info,
            "charts": charts,
            "ds": ds,
            "id": song["id"],
            "level": levels,
            "title": title_with_kanji
        }

        result.append(song_entry)

    return result


def cross(checker: list[Any], elem: Any | list[Any] | None, diff):
    ret = False
    diff_ret = []
    if not elem:
        return True, diff
    if isinstance(elem, list):
        for _j in enumerate(checker):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if __e in elem:
                diff_ret.append(_j)
                ret = True
    elif isinstance(elem, tuple):
        for _j in enumerate(checker):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem[0] <= __e <= elem[1]:
                diff_ret.append(_j)
                ret = True
    else:
        for _j in enumerate(checker):
            if _j >= len(checker):
                continue
            __e = checker[_j]
            if elem == __e:
                return True, [_j]
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
    hold: int | None = None
    slide: int | None = None
    air: int | None = None
    flick: int | None = None
    total: int | None = None
    charter: int | None = None

    def __getattribute__(self, item):
        if item == "tap":
            return self["notes"][0]
        if item == "hold":
            return self["notes"][1]
        if item == "slide":
            return self["notes"][2]
        if item == "air":
            return self["notes"][3]
        if item == "flick":
            return self["notes"][4]
        if item == "total":
            return sum(self["notes"])
        if item == "charter":
            return self["charter"]
        return super().__getattribute__(item)


class Music(dict):
    id: str | None = None
    title: str | None = None
    ds: list[float] | None = None
    level: list[str] | None = None
    genre: str | None = None
    bpm: float | None = None
    version: str | None = None
    charts: Chart | None = None
    artist: str | None = None
    diff: list[int] = []

    def __getattribute__(self, item):
        if item in {"genre", "artist", "bpm", "version"}:
            if item == "version":
                return self["basic_info"]["from"]
            return self["basic_info"][item]
        if item in self:
            return self[item]
        return super().__getattribute__(item)


class MusicList(list[Music]):
    def by_id(self, music_id: str) -> Music | None:
        for music in self:
            if music.id == int(music_id):
                return music
        return None

    def by_title(self, music_title: str) -> Music | None:
        for music in self:
            if music.title.lower() == music_title.lower():
                return music
        return None

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
            url = "https://maimai.lxns.net/api/v0/chunithm/song/list?notes=true"
            data = await get_url(url, 200, headers={"User-Agent": "AkariBot/1.0"}, fmt="json")
            if data:
                data = process_lxns_to_diving_fish(data)
                with open(chu_song_info_path, "wb") as f:
                    f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
            return data
        except Exception:
            Logger.exception()
            try:
                with open(chu_song_info_path, "rb") as f:
                    data = orjson.loads(f.read())
                return data
            except Exception:
                return None
