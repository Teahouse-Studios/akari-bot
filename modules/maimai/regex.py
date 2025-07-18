import re

import orjson as json

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import I18NContext, Plain
from core.component import module
from .libraries.maimaidx_apidata import get_info, search_by_alias
from .libraries.maimaidx_mapping import *
from .libraries.maimaidx_music import TotalList
from .libraries.maimaidx_utils import get_diff, get_grade_info
from .maimai import query_alias, query_plate, query_song_score, query_process

total_list = TotalList()

mai_regex = module(
    "maimai_regex",
    desc="{I18N:maimai.help.maimai_regex.desc}",
    doc=True,
    recommend_modules=["maimai"],
    alias="mai_regex",
    developers=["DoroWolf"],
    support_languages=["zh_cn", "zh_tw"],
)


@mai_regex.regex(r"(.+)\s?是什[么麼]歌", desc="{I18N:maimai.help.maimai_regex.song}")
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0]
    if name[:2].lower() == "id":
        sid = name[2:]
    else:
        sid_list = await search_by_alias(name)
        if len(sid_list) == 0:
            await msg.finish(I18NContext("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            msg_chain = MessageChain.assign()
            msg_chain.append(I18NContext("maimai.message.disambiguation"))
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                if s:
                    msg_chain.append(Plain(f"{s["id"]} - {s["title"]}{" (DX)" if s["type"] == "DX" else ""}"))
            await msg.finish(msg_chain)
        else:
            sid = str(sid_list[0])
    music = (await total_list.get()).by_id(sid)
    if not music:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    msg_chain = MessageChain.assign()
    if int(sid) > 100000:
        with open(mai_utage_info_path, "rb") as file:
            utage_data = json.loads(file.read())
        if utage_data:
            try:
                msg_chain.append(Plain(f"「{utage_data[sid]["comment"]}」"))
            except KeyError:
                msg_chain.append(Plain("「Let's party!」"))

        msg_chain.append(I18NContext(
            "maimai.message.song",
            artist=music["basic_info"]["artist"],
            genre="宴會場",
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
            level=music["level"][0]
        ))
    else:
        msg_chain.append(I18NContext(
            "maimai.message.song",
            artist=music["basic_info"]["artist"],
            genre=genre_i18n_mapping.get(
                music["basic_info"]["genre"], music["basic_info"]["genre"]
            ),
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
            level="/".join((str(ds) for ds in music["ds"])),
        ))

    await msg.finish(await get_info(music, msg_chain))


@mai_regex.regex(r"(?:id)?(\d+)\s?有什(?:么别|麼別)[名称稱]", flags=re.I, desc="{I18N:maimai.help.maimai_regex.alias}")
async def _(msg: Bot.MessageSession):
    sid = msg.matched_msg.groups()[0]
    await query_alias(msg, sid)


@mai_regex.regex(r"(.+)\s?有什[么麼]分\s?(.+)?", desc="{I18N:maimai.help.maimai_regex.score}")
async def _(msg: Bot.MessageSession):
    songname = msg.matched_msg.groups()[0]
    username = msg.matched_msg.groups()[1]
    await query_song_score(msg, songname, username)


@mai_regex.regex(r"(\d+\+?)\s?([a-zA-Z]+\+?)\s?[进進]度\s?(.+)?", desc="{I18N:maimai.help.maimai_regex.process}")
async def _(msg: Bot.MessageSession):
    level = msg.matched_msg.groups()[0]
    goal = msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    await query_process(msg, level, goal, username)


@mai_regex.regex(r"(.?)([極极将將舞神者]舞?)[进進]度\s?(.+)?", desc="{I18N:maimai.help.maimai_regex.plate}")
async def _(msg: Bot.MessageSession):
    plate = msg.matched_msg.groups()[0] + msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    await query_plate(msg, plate, username, get_list=False)


@mai_regex.regex(r"(.?)([極极将將舞神者]舞?)完成表\s?(.+)?", desc="{I18N:maimai.help.maimai_regex.plate.list}")
async def _(msg: Bot.MessageSession):
    plate = msg.matched_msg.groups()[0] + msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    await query_plate(msg, plate, username, get_list=True)


@mai_regex.regex(r"(?:随个|隨個)\s?((?:dx|DX|sd|SD|标准|標準)\s?)?([绿綠黄黃红紅紫白]?)\s?([0-9]+\+?)",
                 desc="{I18N:maimai.help.maimai_regex.random}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        try:
            if res.groups()[0] in ["dx", "DX"]:
                tp = ["DX"]
            elif res.groups()[0] in ["sd", "SD", "标准", "標準"]:
                tp = ["SD"]
            else:
                tp = ["SD", "DX"]
            level = res.groups()[2]
            if res.groups()[1] == "":
                music_data = (await total_list.get()).filter(level=level, type=tp)
            else:
                music_data = (await total_list.get()).filter(
                    level=level, diff=[get_diff(res.groups()[1])], type=tp
                )
            if len(music_data) == 0:
                await msg.finish(I18NContext("maimai.message.music_not_found"))
            else:
                music = music_data.random()
                await msg.finish(
                    await get_info(
                        music, Plain(f"\n{"/".join(str(ds) for ds in music.ds)}")
                    )
                )
        except ValueError:
            await msg.finish(I18NContext("maimai.message.random.failed"))


@mai_regex.regex(r"(.+)\s?段位(?:[认認]定)?列?表", desc="{I18N:maimai.help.maimai_regex.grade}")
async def _(msg: Bot.MessageSession):
    grade = msg.matched_msg.groups()[0]
    await get_grade_info(msg, grade)
