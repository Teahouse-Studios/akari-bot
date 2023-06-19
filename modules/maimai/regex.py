import re

from core.logger import Logger
from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from modules.maimai.libraries.maimaidx_api_data import get_alias
from modules.maimai.libraries.maimaidx_music import *

total_list = TotalList()

diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']
diff_label_abbr = ['bas', 'adv', 'exp', 'mas', 'rem']
diff_label_zhs = ['绿', '黄', '红', '紫', '白']
diff_label_zht = ['綠', '黃', '紅']


def song_txt(music: Music):
    return [Plain(f"{music.id} {music.title}{' (DX)' if music['type'] == 'DX' else ''}\n"),
            BImage(f"https://www.diving-fish.com/covers/{get_cover_len5_id(music.id)}.png", ),
            Plain(f"\n{'/'.join(str(ds) for ds in music.ds)}")]


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
                     alias='mai_regex', developers=['DoroWolf'])


@mai_regex.handle(re.compile(r"(.+)\s?是(什么|什麼)歌"), desc='{maimai.help.maimai_regex.song}')
async def _(msg: Bot.MessageSession):
    name = msg.matched_msg.groups()[0].strip()
    if name == "":
        return
    elif name.isdigit():
        music = (await total_list.get()).by_id(name)
        if music is None:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    else:
        sid_list = await get_alias(name, get_music=True)
        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']} {s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            music = (await total_list.get()).by_id(str(sid_list[0]))

    file = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music['id'])}.png"
    await msg.finish(
        [Plain(f"{music['id']} {music['title']} {' (DX)' if music['type'] == 'DX' else ''}\n"),
         BImage(f"{file}"),
         Plain(msg.locale.t("maimai.message.song",
                            artist=music['basic_info']['artist'], genre=music['basic_info']['genre'],
                            bpm=music['basic_info']['bpm'], version=music['basic_info']['from'],
                            level='/'.join((str(ds) for ds in music['ds']))))]) 


@mai_regex.handle(re.compile(r"(随个|隨個)\s?((?:dx|DX|sd|SD|标准|標準)\s?)?([绿綠黄黃红紅紫白]?)\s?([0-9]+\+?)"),
            desc="{maimai.help.maimai_regex.random.filter}")
async def _(msg: Bot.MessageSession):
    res = msg.matched_msg
    if res:
        try:
            if res.groups()[1] in ["dx", "DX"]:
                tp = ["DX"]
            elif res.groups()[1] in ["sd", "SD"] or res.groups()[1] in ["标准", "標準"]:
                tp = ["SD"]
            else:
                tp = ["SD", "DX"]
            level = res.groups()[3]
            if res.groups()[2] == "":
                music_data = (await total_list.get()).filter(level=level, type=tp)
            else:
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(res.groups()[2])],
                                                             type=tp)
            if len(music_data) == 0:
                rand_result = msg.locale.t("maimai.message.music_not_found")
            else:
                rand_result = song_txt(music_data.random())
            await msg.finish(rand_result)
        except Exception as e:
            Logger.error(e)
            await msg.finish(msg.locale.t("maimai.message.random.error"))



@mai_regex.handle(re.compile(r".*\s?(M|m)ai(mai)?\s?.*(什么|什麼)"), desc='{maimai.help.maimai_regex.random}')
async def _(msg: Bot.MessageSession):
    await msg.finish(song_txt((await total_list.get()).random()))
