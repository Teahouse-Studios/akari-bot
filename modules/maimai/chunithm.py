from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.utils.image import msgchain2image
from .dbutils import DivingProberBindInfoManager
from .libraries.chunithm_apidata import get_info
from .libraries.chunithm_music import TotalList
from .libraries.chunithm_utils import generate_best30_text, get_diff, SONGS_PER_PAGE

total_list = TotalList()
diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Ultima']


chu = module('chunithm',
             developers=['DoroWolf'],
             alias='chu', support_languages=['zh_cn'], desc='{chunithm.help.desc}')


@chu.command('base <constant> [<constant_max>] {{maimai.help.base}}')
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
                                   music['level'][i]))

        s = msg.locale.t("maimai.message.base", constant=round(constant, 1)) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B. {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) > 200:
        await msg.finish(msg.locale.t("maimai.message.too_much", length=len(result_set)))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


@chu.command('level <level> [<page>] {{maimai.help.level}}')
async def _(msg: Bot.MessageSession, level: str, page: str = None):
    result_set = []
    data = (await total_list.get()).filter(level=level)
    for music in sorted(data, key=lambda i: int(i['id'])):
        for i in music.diff:
            result_set.append((music['id'],
                               music['title'],
                               music['ds'][i],
                               diff_label[i],
                               music['level'][i]))

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and page.isdigit() else 1
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    s = msg.locale.t("maimai.message.level", level=level) + "\n"
    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]}\u200B. {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"

    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("maimai.message.pages", page=page, total_pages=total_pages)
        img = await msgchain2image([Plain(s)])
        await msg.finish([BImage(img)])


@chu.command('search <keyword> {{maimai.help.search}}')
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
            search_result += f"{music['id']}\u200B. {music['title']}\n"
        if len(res) <= SONGS_PER_PAGE:
            await msg.finish([Plain(search_result.strip())])
        else:
            img = await msgchain2image([Plain(search_result)])
            await msg.finish([BImage(img)])


@chu.command('b30 [<username>] {{chunithm.help.b30}}')
async def _(msg: Bot.MessageSession, username: str = None):
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {'qq': msg.session.sender}
        else:
            username = DivingProberBindInfoManager(msg).get_bind_username()
            if not username:
                await msg.finish(msg.locale.t("chunithm.message.user_unbound", prefix=msg.prefixes[0]))
            payload = {'username': username}
    else:
        payload = {'username': username}

    img = await generate_best30_text(msg, payload)
    await msg.finish([BImage(img)])


@chu.command('id <id> [<diff>] {{maimai.help.id}}')
@chu.command('song <song> [<diff>] {{chunithm.help.song}}')
async def _(msg: Bot.MessageSession, song: str, diff: str = None):
    if '<id>' in msg.parsed_msg:
        sid = msg.parsed_msg['<id>']
        music = (await total_list.get()).by_id(sid)
    elif song[:2].lower() == "id":
        sid = song[2:]
        music = (await total_list.get()).by_id(sid)
    else:
        song = song.replace("_", " ").strip().lower()
        music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if diff:
        diff_index = get_diff(diff)  # diff_index 的结果可能为 0
        if (not diff_index and diff_index != 0) or (len(music['ds']) == 4 and diff_index == 4):
            await msg.finish(msg.locale.t("maimai.message.chart_not_found"))
        chart = music['charts'][diff_index]
        ds = music['ds'][diff_index]
        level = music['level'][diff_index]
        res = msg.locale.t(
                "chunithm.message.song.diff",
                diff=diff_label[diff_index],
                level=level,
                ds=ds,
                combo=chart['combo'],
                charter=chart['charter'])
        await msg.finish(await get_info(msg, music, Plain(res)))
    else:
        res = msg.locale.t(
                "chunithm.message.song",
                artist=music['basic_info']['artist'],
                genre=music['basic_info']['genre'],
                bpm=music['basic_info']['bpm'],
                version=music['basic_info']['from'],
                level='/'.join((str(ds) for ds in music['ds'])))
        await msg.finish(await get_info(msg, music, Plain(res)))


@chu.command('random [<diff+level>] {{maimai.help.random}}')
async def _(msg: Bot.MessageSession):
    condit = msg.parsed_msg.get('<diff+level>', '')
    level = ''
    diff = ''
    try:
        for char in condit:
            if char.isdigit() or char == '+':
                level += char
            else:
                diff += char

        if level == "":
            if diff == "":
                music = (await total_list.get()).random()
                await msg.finish(await get_info(msg, music, Plain(f"{'/'.join(str(ds) for ds in music.ds)}")))
            else:
                raise ValueError
        else:
            if diff == "":
                music_data = (await total_list.get()).filter(level=level)
            else:
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(diff)])

        if len(music_data) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        else:
            music = music_data.random()
            await msg.finish(await get_info(msg, music, Plain(f"{'/'.join(str(ds) for ds in music.ds)}")))
    except (ValueError, TypeError):
        await msg.finish(msg.locale.t("maimai.message.random.error"))
