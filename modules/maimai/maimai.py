import traceback

from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.utils.image import msgchain2image
from .dbutils import DivingProberBindInfoManager
from .libraries.maimaidx_apidata import get_alias, get_info, search_by_alias, update_alias, update_covers
from .libraries.maimaidx_best50 import generate, computeRa
from .libraries.maimaidx_music import TotalList
from .libraries.maimaidx_utils import generate_best50_text, get_diff, get_grade_info, SONGS_PER_PAGE

total_list = TotalList()

diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Re:MASTER']


mai = module('maimai',
             recommend_modules='maimai_regex', developers=['mai-bot', 'OasisAkari', 'DoroWolf'],
             alias='mai', support_languages=['zh_cn'], desc='{maimai.help.desc}')


@mai.command('base <constant> [<constant_max>] {{maimai.help.base}}')
async def _(msg: Bot.MessageSession, constant: float, constant_max: float = None):
    result_set = []
    if constant <= 0:
        await msg.finish(msg.locale.t('maimai.message.level_invalid'))
    if constant_max:
        if constant > constant_max:
            await msg.finish(msg.locale.t('error.range.invalid'))
        result_set = await base_level_q(constant, constant_max)
        s = msg.locale.t(
            "maimai.message.base.range", constant=round(
                constant, 1), constant_max=round(
                constant_max, 1)) + "\n"
    else:
        if constant_max:
            data = (await total_list.get()).filter(ds=(constant, constant_max))
        else:
            data = (await total_list.get()).filter(ds=constant)

        for music in sorted(data, key=lambda i: int(i['id'])):
            for i in music.diff:
                result_set.append((music['id'],
                                   music['title'],
                                   music['ds'][i], 
                                   diff_label[i],
                                   music['level'][i],
                                   music['type']))

        s = msg.locale.t("maimai.message.base", constant=round(constant, 1)) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B. {elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) > 200:
        await msg.finish(msg.locale.t("maimai.message.too_much", length=len(result_set)))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


@mai.command('level <level> [<page>] {{maimai.help.level}}')
async def _(msg: Bot.MessageSession, level: str, page: str = None):
    result_set = []
    data = (await total_list.get()).filter(level=level)
    for music in sorted(data, key=lambda i: int(i['id'])):
        for i in music.diff:
            result_set.append((music['id'],
                               music['title'],
                               music['ds'][i], 
                               diff_label[i], 
                               music['level'][i], 
                               music['type']))

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and page.isdigit() else 1
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    s = msg.locale.t("maimai.message.level", level=level) + "\n"
    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]}\u200B. {elem[1]}{' (DX)' if elem[5] == 'DX' else ''} {elem[3]} {elem[4]} ({elem[2]})\n"

    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("maimai.message.pages", page=page, total_pages=total_pages)
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


@mai.command('new [<page>] {{maimai.help.new}}')
async def _(msg: Bot.MessageSession, page: str = None):
    result_set = []
    data = (await total_list.get()).new()
    
    for music in sorted(data, key=lambda i: int(i['id'])):
        result_set.append((music['id'],
                           music['title'],
                           music['type']))

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and page.isdigit() else 1
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    s = msg.locale.t("maimai.message.new") + "\n"
    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]}\u200B. {elem[1]}{' (DX)' if elem[2] == 'DX' else ''}\n"

    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("maimai.message.pages", page=page, total_pages=total_pages)
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


@mai.command('search <keyword> {{maimai.help.search}}')
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    res = (await total_list.get()).filter(title_search=name)
    if len(res) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(res) > 200:
        await msg.finish(msg.locale.t("maimai.message.too_much", length=len(res)))
    else:
        result = msg.locale.t("maimai.message.search", keyword=name) + "\n"
        for music in sorted(res, key=lambda i: int(i['id'])):
            result += f"{music['id']}\u200B. {music['title']}{' (DX)' if music['type'] == 'DX' else ''}\n"
        if len(res) <= SONGS_PER_PAGE:
            await msg.finish([Plain(result.strip())])
        else:
            img = await msgchain2image([Plain(result)])
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

    title = f"{music['id']}\u200B. {music['title']}{' (DX)' if music['type'] == 'DX' else ''}"
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


@mai.command(['b50 [<username>] {{maimai.help.b50}}',
             'b50 beta [<username>] {{maimai.help.b50.beta}}'])
async def _(msg: Bot.MessageSession, username: str = None):
    beta = True
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender, 'b50': True}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("maimai.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username, 'b50': True}
    else:
        payload = {'username': username, 'b50': True}

    if not msg.parsed_msg.get('beta', False):
        try:
            img = await generate(msg, payload)
            beta = False
        except:
            traceback.print_exc()
    if beta:
        img = await generate_best50_text(msg, payload)
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
        diff_index = get_diff(diff)  # diff_index 的输出结果可能为 0
        if (not diff_index and diff_index != 0) or (len(music['ds']) == 4 and diff_index == 4):
            await msg.finish(msg.locale.t("maimai.message.chart_not_found"))
        chart = music['charts'][diff_index]
        ds = music['ds'][diff_index]
        level = music['level'][diff_index]
        if len(chart['notes']) == 4:
            res = msg.locale.t(
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
            res = msg.locale.t(
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
        await msg.finish(await get_info(msg, music, Plain(res)))
    else:
        res = msg.locale.t(
            "maimai.message.song",
            artist=music['basic_info']['artist'],
            genre=music['basic_info']['genre'],
            bpm=music['basic_info']['bpm'],
            version=music['basic_info']['from'],
            level='/'.join((str(ds) for ds in music['ds'])))
        await msg.finish(await get_info(msg, music, Plain(res)))


@mai.command('random <diff+level> [<dx_type>] {{maimai.help.random.filter}}')
async def _(msg: Bot.MessageSession, dx_type: str = None):
    condit = msg.parsed_msg['<diff+level>']
    level = ''
    diff = ''
    try:
        if dx_type in ["dx", "DX"]:
            dx_type = ["DX"]
        elif dx_type in ["sd", "SD", "标准", "標準"]:
            dx_type = ["SD"]
        else:
            dx_type = ["SD", "DX"]

        for char in condit:
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
            await msg.finish(await get_info(msg, music, Plain(f"{'/'.join(str(ds) for ds in music.ds)}")))
    except (ValueError, TypeError):
        await msg.finish(msg.locale.t("maimai.message.random.error"))


@mai.command('random {{maimai.help.random}}')
async def _(msg: Bot.MessageSession):
    music = (await total_list.get()).random()
    await msg.finish(await get_info(msg, music, Plain(f"{'/'.join(str(ds) for ds in music.ds)}")))


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
