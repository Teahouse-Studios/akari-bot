import re

from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from .libraries.maimaidx_apidata import get_alias, get_info, search_by_alias
from .libraries.maimaidx_music import TotalList
from .libraries.maimaidx_utils import get_diff, get_grade_info

total_list = TotalList()


mai_regex = module('maimai_regex',
                   desc='{maimai.help.maimai_regex.desc}',
                   recommend_modules=['maimai'],
                   alias='mai_regex',
                   developers=['DoroWolf'],
                   support_languages=['zh_cn', 'zh_tw'])


@mai_regex.regex(re.compile(r"(.+)\s?是什[么麼]歌"), desc='{maimai.help.maimai_regex.song}')
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0]
    if name[:2].lower() == "id":
        sid = name[2:]
    else:
        sid_list = await search_by_alias(msg, name)
        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']}\u200B. {s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            sid = str(sid_list[0])
    music = (await total_list.get()).by_id(sid)
    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    await msg.finish(await get_info(msg, music, Plain(msg.locale.t("maimai.message.song",
                                                                   artist=music['basic_info']['artist'],
                                                                   genre=music['basic_info']['genre'],
                                                                   bpm=music['basic_info']['bpm'],
                                                                   version=music['basic_info']['from'],
                                                                   level='/'.join((str(ds) for ds in music['ds']))))))


@mai_regex.regex(re.compile(r"(?:id)?(\d+)\s?有什(?:么别|麼別)名", flags=re.I), desc='{maimai.help.maimai_regex.alias}')
async def _(msg: Bot.MessageSession):
    sid = msg.matched_msg.groups()[0]
    music = (await total_list.get()).by_id(sid)
    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    title = f"{music['id']}\u200B. {music['title']}{' (DX)' if music['type'] == 'DX' else ''}"
    alias = await get_alias(msg, sid)
    if len(alias) == 0:
        await msg.finish(msg.locale.t("maimai.message.alias.alias_not_found"))
    else:
        result = msg.locale.t("maimai.message.alias", title=title) + "\n"
        result += "\n".join(alias)
        await msg.finish([Plain(result.strip())])


@mai_regex.regex(re.compile(r"(?:随个|隨個)\s?((?:dx|DX|sd|SD|标准|標準)\s?)?([绿綠黄黃红紅紫白]?)\s?([0-9]+\+?)"),
                 desc="{maimai.help.maimai_regex.random}")
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
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(res.groups()[1])],
                                                             type=tp)
            if len(music_data) == 0:
                await msg.finish(msg.locale.t("maimai.message.music_not_found"))
            else:
                music = music_data.random()
                await msg.finish(await get_info(msg, music, Plain(f"\n{'/'.join(str(ds) for ds in music.ds)}")))
        except ValueError:
            await msg.finish(msg.locale.t("maimai.message.random.failed"))


@mai_regex.regex(re.compile(r"(.+)\s?段位[认認]定列?表"), desc='{maimai.help.maimai_regex.grade}')
async def _(msg: Bot.MessageSession):
    grade = msg.matched_msg.groups()[0]
    await get_grade_info(msg, grade)
