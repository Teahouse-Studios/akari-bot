import re
import traceback

from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.logger import Logger
from core.utils.image import msgchain2image
from modules.maimai.libraries.apidata import get_alias, get_info, search_by_alias
from modules.maimai.libraries.music import get_cover_len5_id, TotalList
from modules.maimai.libraries.utils import get_grade_info, get_level_process, get_plate_process, get_player_score

goal_list = ["A", "AA", "AAA", "S", "S+", "SS", "SS+", "SSS", "SSS+", 
             "FC", "FC+", "AP", "AP+", "FS", "FS+", "FDX", "FDX+"]
level_list = ['1', '2', '3', '4', '5', '6', '7', '7+', '8', '8+', '9', '9+',
              '10', '10+', '11', '11+', '12', '12+', '13', '13+', '14', '14+', '15']
total_list = TotalList()

diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']
diff_label_abbr = ['bas', 'adv', 'exp', 'mas', 'rem']
diff_label_zhs = ['绿', '黄', '红', '紫', '白']
diff_label_zht = ['綠', '黃', '紅']


def get_diff(diff):
    diff = diff.lower()
    diff_label_lower = [label.lower() for label in diff_label]

    if diff in diff_label_zhs:
        level = diff_label_zhs.index(diff)
    elif diff in diff_label_zht:
        level = diff_label_zht.index(diff)
    elif diff in diff_label_abbr:
        level = diff_label_abbr.index(diff)
    elif diff in diff_label_lower:
        level = diff_label_lower.index(diff)
    else:
        level = None
    return level


mai_regex = module('maimai_regex',
                   desc='{maimai.help.maimai_regex.desc}', recommend_modules=['maimai'],
                   alias='mai_regex', developers=['DoroWolf'], support_languages=['zh_cn', 'zh_tw'])


@mai_regex.regex(re.compile(r"(.+)\s?是什[么麼]歌"), desc='{maimai.help.maimai_regex.song}')
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0]
    if name[:2].lower() == "id":
        sid = name[2:]
        music = (await total_list.get()).by_id(sid)
        if not music:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
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
            music = (await total_list.get()).by_id(str(sid_list[0]))
            if not music:
                await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    await msg.finish(await get_info(msg, music, Plain(msg.locale.t("maimai.message.song",
                                                                   artist=music['basic_info']['artist'],
                                                                   genre=music['basic_info']['genre'],
                                                                   bpm=music['basic_info']['bpm'],
                                                                   version=music['basic_info']['from'],
                                                                   level='/'.join((str(ds) for ds in music['ds']))))))


@mai_regex.regex(re.compile(r"(.+)\s?有什[么麼]分\s?(.+)?"), desc='{maimai.help.maimai_regex.info}')
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0]
    username = msg.matched_msg.groups()[1]
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

    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    output = await get_player_score(msg, payload, sid)

    await msg.finish(await get_info(msg, music, Plain(output)))


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
            await msg.finish(msg.locale.t("maimai.message.random.error"))


@mai_regex.regex(re.compile(r"(.?)([極极将舞神者]舞?)[进進]度\s?(.+)?"), desc='{maimai.help.maimai_regex.plate}')
async def _(msg: Bot.MessageSession):
    plate = msg.matched_msg.groups()[0] + msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    if plate in ['真将', '真將'] or (plate[1] == '者' and plate[0] != '霸'):
        return

    output, get_img = await get_plate_process(msg, payload, plate)

    if get_img:
        img = await msgchain2image([Plain(output)], msg)
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai_regex.regex(re.compile(r"([0-9]+\+?)\s?(.+)\s?[进進]度\s?(.+)?"), desc='{maimai.help.maimai_regex.process}')
async def _(msg: Bot.MessageSession):
    level = msg.matched_msg.groups()[0]
    goal = msg.matched_msg.groups()[1]
    username = msg.matched_msg.groups()[2]
    if not goal:
        return
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    if level in level_list:
        level_num = int(level.split('+')[0])
        if level_num < 8:
            return
    else:
        return

    if goal.upper() not in goal_list:
        await msg.finish(msg.locale.t("maimai.message.goal_invalid"))

    output, get_img = await get_level_process(msg, payload, level, goal)

    if get_img:
        img = await msgchain2image([Plain(output)], msg)
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai_regex.regex(re.compile(r"(.+)\s?段位[认認]定列?表"), desc='{maimai.help.maimai_regex.grade}')
async def _(msg: Bot.MessageSession):
    grade = msg.matched_msg.groups()[0]
    await get_grade_info(msg, grade)