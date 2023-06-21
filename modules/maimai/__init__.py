from core.builtins import Bot, Plain, Image as BImage
from core.builtins import command_prefix
from core.component import module
from core.logger import Logger
from core.utils.image import msgchain2image
from modules.maimai.libraries.maimai_best_50 import generate
from modules.maimai.libraries.maimaidx_api_data import get_alias
from modules.maimai.libraries.maimaidx_project import get_rank, get_player_score, get_level_process
from modules.maimai.libraries.maimaidx_music import *
from .regex import *

total_list = TotalList()

diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']
diff_label_abbr = ['bas', 'adv', 'exp', 'mas', 'rem']
diff_label_zhs = ['绿', '黄', '红', '紫', '白']
diff_label_zht = ['綠', '黃', '紅']


def song_txt(music: Music):
    return [Plain(f"{music.id}\u200B.{music.title}{' (DX)' if music['type'] == 'DX' else ''}\n"),
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


mai = module('maimai', developers=['mai-bot', 'OasisAkari', 'DoroWolf'], alias='mai',
             desc='{maimai.help.desc}')


@mai.handle('level <level> {{maimai.help.level}}')
async def _(msg: Bot.MessageSession, level: str):
    result_set = await diff_level_q(level)
    s = msg.locale.t("maimai.message.level", level=level) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B.{elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        return await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    if len(result_set) <= 10:
        await msg.finish(s.strip())
    else:
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


async def diff_level_q(level):
    result_set = []
    music_data = (await total_list.get()).filter(level=level)
    for music in sorted(music_data, key=lambda i: int(i['id'])):
        for i in music.diff:
            result_set.append(
                (music['id'],
                 music['title'],
                 music['ds'][i],
                 diff_label[i],
                 music['level'][i],
                 music['type']))
    return result_set


@mai.handle('base <rating> [<rating_max>] {{maimai.help.base}}')
async def _(msg: Bot.MessageSession, rating: float, rating_max: float = None):
    if rating_max is not None:
        if rating > rating_max:
            return await msg.finish(msg.locale.t('error.range.invalid'))
        result_set = await base_level_q(rating, rating_max)
        s = msg.locale.t("maimai.message.base.range", rating=round(rating, 1), rating_max=round(rating_max, 1)) + "\n"
    else:
        result_set = await base_level_q(rating)
        s = msg.locale.t("maimai.message.base", rating=round(rating, 1)) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B.{elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        return await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    if len(result_set) > 200:
        return await msg.finish(msg.locale.t("maimai.message.too_much", length=len(result_set)))
    if len(result_set) <= 10:
        await msg.finish(s.strip())
    else:
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


async def base_level_q(ds1, ds2=None):
    result_set = []
    if ds2 is not None:
        music_data = (await total_list.get()).filter(ds=(ds1, ds2))
    else:
        music_data = (await total_list.get()).filter(ds=ds1)
    for music in sorted(music_data, key=lambda i: int(i['id'])):
        for i in music.diff:
            result_set.append(
                (music['id'],
                 music['title'],
                 music['ds'][i],
                 diff_label[i],
                 music['level'][i],
                 music['type']))
    return result_set


@mai.handle('search <keyword> {{maimai.help.search}}')
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    res = (await total_list.get()).filter(title_search=name)
    if len(res) == 0:
        return await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    if len(res) > 200:
        return await msg.finish(msg.locale.t("maimai.message.too_much", length=len(res)))
    else:
        search_result = msg.locale.t("maimai.message.search", keyword=name) + "\n"
        for music in sorted(res, key=lambda i: int(i['id'])):
            search_result += f"{music['id']}\u200B.{music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"
        if len(res) <= 10:
            await msg.finish([Plain(search_result.strip())])
        else:
            img = await msgchain2image([Plain(search_result)])
            await msg.finish([BImage(img)])


@mai.handle('alias <sid> {{maimai.help.alias}}')
async def _(msg: Bot.MessageSession, sid: str):
    if not sid.isdigit():
        await msg.finish(msg.locale.t('maimai.message.error.non_digital'))
    music = (await total_list.get()).by_id(sid)
    if not music:
        return await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    title = f"{music['id']}\u200B.{music['title']}{' (DX)' if music['type'] == 'DX' else ''}"
    alias = await get_alias(sid)
    if len(alias) == 0:
        return await msg.finish(msg.locale.t("maimai.message.alias_not_found"))
    else:
        result = msg.locale.t("maimai.message.alias", title=title) + "\n"
        result += "\n".join(alias)
        await msg.finish([Plain(result.strip())])


@mai.handle('b50 [<username>] {{maimai.help.b50}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if username is None and msg.target.senderFrom == "QQ":
        payload = {'qq': msg.session.sender, 'b50': True}
    else:
        if username is None:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username, 'b50': True}
    img = await generate(msg, payload)
    await msg.finish([BImage(img)])    


@mai.handle('info <id_or_alias> [<username>] {{maimai.help.info}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, username: str = None):
    if id_or_alias.isdigit():
        sid = id_or_alias
    else:
        sid_list = await get_alias(id_or_alias, get_music=True)
        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']}\u200B.{s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            sid = str(sid_list[0])

    music = (await total_list.get()).by_id(sid)
    if music is None:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if username is None and msg.target.senderFrom == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if username is None:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    output = await get_player_score(msg, payload, sid)

    file = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music['id'])}.png"
    await msg.finish(
        [Plain(f"{music['id']}\u200B.{music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"),
         BImage(f"{file}"), Plain(output)])
    

@mai.handle('process <process> <goal> [<username>]{{maimai.help.process}}')
async def _(msg: Bot.MessageSession, process: str, goal: str, username: str = None):
    if username is None and msg.target.senderFrom == "QQ":
        payload = {'qq': msg.session.sender, 'b50': True}
    else:
        if username is None:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username, 'b50': True}

    output = await get_level_process(msg, payload, process, goal)

    await msg.finish(output)



@mai.handle('rank [<username>] {{maimai.help.rank}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if username is None and msg.target.senderFrom == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if username is None:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    result = await get_rank(msg, payload)
    time, total_rank, average_rating, username, rating, rank, surpassing_rate = result
    formatted_average_rating = "{:.4f}".format(average_rating)
    formatted_surpassing_rate = "{:.2f}".format(surpassing_rate)

    await msg.finish(msg.locale.t('maimai.message.rank', time=time, total_rank=total_rank, user=username,
                                  rating=rating, rank=rank, average_rating=formatted_average_rating,
                                  surpassing_rate=formatted_surpassing_rate))


@mai.handle('random <diff+level> [<dx_type>] {{maimai.help.random.filter}}')
async def _(msg: Bot.MessageSession, dx_type: str = None):
    filter = msg.parsed_msg['<diff+level>']
    level = ''
    diff = ''
    try:
        if dx_type in ["dx", "DX"]:
            dx_type = ["DX"]
        elif dx_type in ["sd", "SD", "标准", "標準"]:
            dx_type = ["SD"]
        else:
            dx_type = ["SD", "DX"]

        for char in filter:
            if char.isdigit() or char == '+':
                level += char
            else:
                diff += char

        if level == "":
            if diff == "#":
                music_data = (await total_list.get()).filter(type=dx_type)
            else:
                raise ValueError
        else:
            if diff == "":
                music_data = (await total_list.get()).filter(level=level, type=dx_type)
            else:
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(diff)], type=dx_type)

        if len(music_data) == 0:
            rand_result = msg.locale.t("maimai.message.music_not_found")
        else:
            rand_result = song_txt(music_data.random())
        await msg.finish(rand_result)
    except Exception as e:
        Logger.error(e)
        await msg.finish(msg.locale.t("maimai.message.random.error"))


@mai.handle('random {{maimai.help.random}}')
async def _(msg: Bot.MessageSession):
    await msg.finish(song_txt((await total_list.get()).random()))


@mai.handle('song <id_or_alias> [<diff>] {{maimai.help.song}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, diff: str = None):
    if id_or_alias.isdigit():
        sid = id_or_alias
    else:
        sid_list = await get_alias(id_or_alias, get_music=True)
        if len(sid_list) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        elif len(sid_list) > 1:
            res = msg.locale.t("maimai.message.song.prompt") + "\n"
            for sid in sorted(sid_list, key=int):
                s = (await total_list.get()).by_id(sid)
                res += f"{s['id']}\u200B.{s['title']}{' (DX)' if s['type'] == 'DX' else ''}\n"
            await msg.finish(res.strip())
        else:
            sid = str(sid_list[0])
    music = (await total_list.get()).by_id(sid)
    if music is None:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if diff is not None:
        diff_index = get_diff(diff)
        if len(music['ds']) == 4 and diff_index == 4:
            await msg.finish(msg.locale.t("maimai.message.chart_not_found"))
        chart = music['charts'][diff_index]
        ds = music['ds'][diff_index]
        level = music['level'][diff_index]
        file = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music['id'])}.png"
        if len(chart['notes']) == 4:
            message = msg.locale.t(
                "maimai.message.song.sd",
                diff=diff_label[diff_index],
                level=level,
                ds=ds,
                tap=chart['notes'][0],
                hold=chart['notes'][1],
                slide=chart['notes'][2],
                brk=chart['notes'][3],
                charter=chart['charter'])
        else:
            message = msg.locale.t(
                "maimai.message.song.dx",
                diff=diff_label[diff_index],
                level=level,
                ds=ds,
                tap=chart['notes'][0],
                hold=chart['notes'][1],
                slide=chart['notes'][2],
                touch=chart['notes'][3],
                brk=chart['notes'][4],
                charter=chart['charter'])
        await msg.finish(
            [Plain(f"{music['id']}\u200B.{music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"),
             BImage(f"{file}"), Plain(message)])
    else:
        file = f"https://www.diving-fish.com/covers/{get_cover_len5_id(music['id'])}.png"
        await msg.finish(
            [Plain(f"{music['id']}\u200B.{music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"),
             BImage(f"{file}"),
             Plain(msg.locale.t("maimai.message.song",
                                    artist=music['basic_info']['artist'], genre=music['basic_info']['genre'],
                                    bpm=music['basic_info']['bpm'], version=music['basic_info']['from'],
                                    level='/'.join((str(ds) for ds in music['ds']))))]) 


@mai.handle('scoreline <sid> <diff> <scoreline> {{maimai.help.scoreline}}')
async def _(msg: Bot.MessageSession, diff: str, sid: str, scoreline: float):
    try:
        diff_index = get_diff(diff)
        music = (await total_list.get()).by_id(sid)
        chart: Dict[Any] = music['charts'][diff_index]
        tap = int(chart['notes'][0])
        slide = int(chart['notes'][2])
        hold = int(chart['notes'][1])
        touch = int(chart['notes'][3]) if len(chart['notes']) == 5 else 0
        brk = int(chart['notes'][-1])
        total_score = 500 * tap + slide * 1500 + hold * 1000 + touch * 500 + brk * 2500
        break_bonus = 0.01 / brk
        break_50_reduce = total_score * break_bonus / 4
        reduce = 101 - scoreline
        if reduce <= 0 or reduce >= 101:
            raise ValueError
        tap_great = "{:.2f}".format(total_score * reduce / 10000)
        tap_great_prop = "{:.4f}".format(10000 / total_score)
        b2t_great = "{:.3f}".format(break_50_reduce / 100)
        b2t_great_prop = "{:.4f}".format(break_50_reduce / total_score * 100)
        await msg.finish(f'''{music['title']}{' (DX)' if music['type'] == 'DX' else ''} {diff_label[diff_index]}
{msg.locale.t('maimai.message.scoreline',
                scoreline=scoreline,
                tap_great=tap_great,
                tap_great_prop=tap_great_prop,
                brk=brk,
                b2t_great=b2t_great,
                b2t_great_prop=b2t_great_prop)}''')
    except Exception:
        await msg.finish(msg.locale.t('maimai.message.scoreline.error', prefix=command_prefix[0]))