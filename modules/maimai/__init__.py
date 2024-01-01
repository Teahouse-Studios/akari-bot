import traceback

from config import Config
from core.builtins import Bot, Plain, Image as BImage
from core.scheduler import CronTrigger
from core.utils.image import msgchain2image
from modules.maimai.libraries.best50 import computeRa, generate
from modules.maimai.libraries.apidata import get_alias, get_info, search_by_alias, update_alias, update_covers
from modules.maimai.libraries.music import get_cover_len5_id, TotalList
from modules.maimai.libraries.utils import get_grade_info, get_level_process, \
    get_plate_process, get_player_score, get_rank, get_score_list
from .regex import *

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


mai = module('maimai',
             recommend_modules='maimai_regex', developers=['mai-bot', 'OasisAkari', 'DoroWolf'],
             alias='mai', support_languages=['zh_cn'], desc='{maimai.help.desc}')


@mai.command('base <constant> [<constant_max>] {{maimai.help.base}}')
async def _(msg: Bot.MessageSession, constant: float, constant_max: float = None):
    if constant_max:
        if constant > constant_max:
            await msg.finish(msg.locale.t('error.range.invalid'))
        result_set = await base_level_q(constant, constant_max)
        s = msg.locale.t(
            "maimai.message.base.range", constant=round(
                constant, 1), constant_max=round(
                constant_max, 1)) + "\n"
    else:
        result_set = await base_level_q(constant)
        s = msg.locale.t("maimai.message.base", constant=round(constant, 1)) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B. {elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) > 200:
        await msg.finish(msg.locale.t("maimai.message.too_much", length=len(result_set)))
    elif len(result_set) <= 10:
        await msg.finish(s.strip())
    else:
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


async def base_level_q(ds1, ds2=None):
    result_set = []
    if ds2:
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


@mai.command('level <level> {{maimai.help.level}}')
async def _(msg: Bot.MessageSession, level: str):
    result_set = await diff_level_q(level)
    s = msg.locale.t("maimai.message.level", level=level) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B. {elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= 10:
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


@mai.command('search <keyword> {{maimai.help.search}}')
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    res = (await total_list.get()).filter(title_search=name)
    if len(res) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(res) > 200:
        await msg.finish(msg.locale.t("maimai.message.too_much", length=len(res)))
    else:
        search_result = msg.locale.t("maimai.message.search", keyword=name) + "\n"
        for music in sorted(res, key=lambda i: int(i['id'])):
            search_result += f"{music['id']}\u200B. {music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"
        if len(res) <= 10:
            await msg.finish([Plain(search_result.strip())])
        else:
            img = await msgchain2image([Plain(search_result)])
            await msg.finish([BImage(img)])


@mai.command('alias <sid> {{maimai.help.alias}}')
async def _(msg: Bot.MessageSession, sid: str):
    if not sid.isdigit():
        if sid[:2].lower() == "id":
            sid = sid[2:]
        else:
            await msg.finish(msg.locale.t('maimai.message.error.non_digital'))

    music = (await total_list.get()).by_id(sid)
    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    title = await get_info(msg, music, cover=False)
    alias = await get_alias(msg, sid)
    if len(alias) == 0:
        await msg.finish(msg.locale.t("maimai.message.alias.alias_not_found"))
    else:
        result = msg.locale.t("maimai.message.alias", title=title) + "\n"
        result += "\n".join(alias)
        await msg.finish([Plain(result.strip())])


@mai.command('grade <grade> {{maimai.help.grade}}')
async def _(msg: Bot.MessageSession, grade: str):
    await get_grade_info(msg, grade)


@mai.command('b50 [<username>] {{maimai.help.b50}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender, 'b50': True}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username, 'b50': True}
    img = await generate(msg, payload)
    await msg.finish([BImage(img)])


@mai.command('id <id> [<diff>] {{maimai.help.id}}')
@mai.command('song <id_or_alias> [<diff>] {{maimai.help.song}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, diff: str = None):
    if '<id>' in msg.parsed_msg:
        sid = msg.parsed_msg['<id>']
    elif id_or_alias[:2].lower() == "id":
        sid = id_or_alias[2:]
    else:
        sid_list = await search_by_alias(msg, id_or_alias)
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

    if diff:
        diff_index = get_diff(diff)
        if not diff_index or (len(music['ds']) == 4 and diff_index == 4):
            await msg.finish(msg.locale.t("maimai.message.chart_not_found"))
        chart = music['charts'][diff_index]
        ds = music['ds'][diff_index]
        level = music['level'][diff_index]
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
        await msg.finish(await get_info(msg, music, Plain(message)))
    else:
        message = msg.locale.t(
            "maimai.message.song",
            artist=music['basic_info']['artist'],
            genre=music['basic_info']['genre'],
            bpm=music['basic_info']['bpm'],
            version=music['basic_info']['from'],
            level='/'.join((str(ds) for ds in music['ds'])))
        await msg.finish(await get_info(msg, music, Plain(message)))


@mai.command('info <id_or_alias> [<username>] {{maimai.help.info}}')
async def _(msg: Bot.MessageSession, id_or_alias: str, username: str = None):
    if id_or_alias[:2].lower() == "id":
        sid = id_or_alias[2:]
    else:
        sid_list = await search_by_alias(msg, id_or_alias)

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


@mai.command('plate <plate> [<username>] {{maimai.help.plate}}')
async def _(msg: Bot.MessageSession, plate: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    if plate in ['真将', '真將'] or (plate[1] == '者' and plate[0] != '霸'):
        await msg.finish(msg.locale.t('maimai.message.plate.plate_not_found'))

    output, get_img = await get_plate_process(msg, payload, plate)

    if get_img:
        img = await msgchain2image([Plain(output)])
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai.command('process <level> <goal> [<username>] {{maimai.help.process}}')
async def _(msg: Bot.MessageSession, level: str, goal: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    if level in level_list:
        level_num = int(level.split('+')[0])
        if level_num < 8:
            await msg.finish(msg.locale.t("maimai.message.process.less_than_8"))
    else:
        await msg.finish(msg.locale.t("maimai.message.level_invalid"))

    if goal.upper() not in goal_list:
        await msg.finish(msg.locale.t("maimai.message.goal_invalid"))

    output, get_img = await get_level_process(msg, payload, level, goal)

    if get_img:
        img = await msgchain2image([Plain(output)])
        await msg.finish([BImage(img)])
    else:
        await msg.finish(output.strip())


@mai.command('rank [<username>] {{maimai.help.rank}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    await get_rank(msg, payload)


@mai.command('scorelist <level> [<username>] {{maimai.help.scorelist}}')
async def _(msg: Bot.MessageSession, level: str, username: str = None):
    if not username and msg.target.sender_from == "QQ":
        payload = {'qq': msg.session.sender}
    else:
        if not username:
            await msg.finish(msg.locale.t("maimai.message.no_username"))
        payload = {'username': username}

    res, get_img = await get_score_list(msg, payload, level)

    if get_img:
        img = await msgchain2image([Plain(res)])
        await msg.finish([BImage(img)])
    else:
        await msg.finish([Plain(res.strip())])


@mai.command('random <diff+level> [<dx_type>] {{maimai.help.random.filter}}')
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
            if diff == "*":
                music_data = (await total_list.get()).filter(type=dx_type)
            else:
                raise ValueError
        else:
            if diff == "":
                music_data = (await total_list.get()).filter(level=level, type=dx_type)
            else:
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(diff)], type=dx_type)

        if len(music_data) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        else:
            music = music_data.random()
            await msg.finish(await get_info(msg, music, Plain(f"\n{'/'.join(str(ds) for ds in music.ds)}")))
    except ValueError:
        await msg.finish(msg.locale.t("maimai.message.random.error"))


@mai.command('random {{maimai.help.random}}')
async def _(msg: Bot.MessageSession):
    music = (await total_list.get()).random()
    await msg.finish(await get_info(msg, music, Plain(f"\n{'/'.join(str(ds) for ds in music.ds)}")))


@mai.command('scoreline <sid> <diff> <score> {{maimai.help.scoreline}}')
async def _(msg: Bot.MessageSession, diff: str, sid: str, score: float):
    try:
        if not sid.isdigit():
            if sid[:2].lower() == "id":
                sid = sid[2:]
            else:
                await msg.finish(msg.locale.t('maimai.message.error.non_digital'))
        diff_index = get_diff(diff)
        music = (await total_list.get()).by_id(sid)
        chart = music['charts'][diff_index]
        tap = int(chart['notes'][0])
        slide = int(chart['notes'][2])
        hold = int(chart['notes'][1])
        touch = int(chart['notes'][3]) if len(chart['notes']) == 5 else 0
        brk = int(chart['notes'][-1])
        total_score = 500 * tap + slide * 1500 + hold * 1000 + touch * 500 + brk * 2500    # 基础分
        bonus_score = total_score * 0.01 / brk    # 奖励分
        break_2550_reduce = bonus_score * 0.25    # 一个 BREAK 2550 减少 25% 奖励分
        break_2000_reduce = bonus_score * 0.6 + 500    # 一个 BREAK 2000 减少 500 基础分和 60% 奖励分
        reduce = 101 - score    # 理论值与给定完成率的差，以百分比计
        if reduce <= 0 or reduce >= 101:
            raise ValueError
        tap_great = "{:.2f}".format(total_score * reduce / 10000)  # 一个 TAP GREAT 减少 100 分
        tap_great_prop = "{:.4f}".format(10000 / total_score)
        b2t_2550_great = "{:.3f}".format(break_2550_reduce / 100)  # 一个 TAP GREAT 减少 100 分
        b2t_2550_great_prop = "{:.4f}".format(break_2550_reduce / total_score * 100)
        b2t_2000_great = "{:.3f}".format(break_2000_reduce / 100)  # 一个 TAP GREAT 减少 100 分
        b2t_2000_great_prop = "{:.4f}".format(break_2000_reduce / total_score * 100)
        await msg.finish(f'''{music['title']}{' (DX)' if music['type'] == 'DX' else ''} {diff_label[diff_index]}
{msg.locale.t('maimai.message.scoreline',
              scoreline=score,
              tap_great=tap_great,
              tap_great_prop=tap_great_prop,
              brk=brk,
              b2t_2550_great=b2t_2550_great,
              b2t_2550_great_prop=b2t_2550_great_prop,
              b2t_2000_great=b2t_2000_great,
              b2t_2000_great_prop=b2t_2000_great_prop)}''')
    except ValueError:
        await msg.finish(msg.locale.t('maimai.message.scoreline.error', prefix=msg.prefixes[0]))


@mai.command('rating <base> <score> {{maimai.help.rating}}')
async def _(msg: Bot.MessageSession, base: float, score: float):
    if score:
        await msg.finish([Plain(max(0, computeRa(base, score)))])


@mai.command('update', required_superuser=True)
async def _(msg: Bot.MessageSession):
    if await update_alias() and await update_covers():
        await msg.finish(msg.locale.t("success"))
    else:
        await msg.finish(msg.locale.t("failed"))


@mai.schedule(CronTrigger.from_crontab('0 0 * * *'))
async def _():
    Logger.info('Updating maimai alias...')
    try:
        await update_alias()
    except Exception:
        if Config('debug'):
            Logger.error(traceback.format_exc())
