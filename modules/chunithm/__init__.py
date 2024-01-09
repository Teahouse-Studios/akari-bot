from config import Config
from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.utils.image import msgchain2image
from modules.chunithm.libraries.music import Music, TotalList

total_list = TotalList()

diff_label = ['Basic', 'Advanced', 'Expert', 'Master', 'Ultima']
diff_label_abbr = ['bas', 'adv', 'exp', 'mas', 'ult']
diff_label_zhs = ['绿', '黄', '红', '紫', '黑']
diff_label_zht = ['綠', '黃', '紅']

SONGS_PER_PAGE = Config('maimai_songs_per_page', 20)

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


async def get_info(msg: Bot.MessageSession, music: Music, *details):
    info = [Plain(f"{music.id}\u200B. {music.title}")]
    # 此处未来会添加图片
    if details:
        info.extend(details)
    return info


chu = module('chunithm',
             developers=['DoroWolf'],
             alias='chu', support_languages=['zh_cn'], desc='{chunithm.help.desc}')


@chu.command('base <constant> [<constant_max>] {{chunithm.help.base}}')
async def _(msg: Bot.MessageSession, constant: float, constant_max: float = None):
    if constant_max:
        if constant > constant_max:
            await msg.finish(msg.locale.t('error.range.invalid'))
        result_set = await base_level_q(constant, constant_max)
        s = msg.locale.t(
            "chunithm.message.base.range", constant=round(
                constant, 1), constant_max=round(
                constant_max, 1)) + "\n"
    else:
        result_set = await base_level_q(constant)
        s = msg.locale.t("chunithm.message.base", constant=round(constant, 1)) + "\n"
    for elem in result_set:
        s += f"{elem[0]}\u200B. {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("chunithm.message.music_not_found"))
    elif len(result_set) > 200:
        await msg.finish(msg.locale.t("chunithm.message.too_much", length=len(result_set)))
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
                 music['level'][i]))
    return result_set


@chu.command('level <level> [<page>] {{chunithm.help.level}}')
async def _(msg: Bot.MessageSession, level: str, page: str=None):
    result_set = await diff_level_q(level)

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and page.isdigit() else 1
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    s = msg.locale.t("chunithm.message.level", level=level) + "\n"
    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]}\u200B. {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"

    if len(result_set) == 0:
        await msg.finish(msg.locale.t("chunithm.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("chunithm.message.pages", page=page, total_pages=total_pages)
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
                 music['level'][i]))
    return result_set


@chu.command('search <keyword> {{chunithm.help.search}}')
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    res = (await total_list.get()).filter(title_search=name)
    if len(res) == 0:
        await msg.finish(msg.locale.t("chunithm.message.music_not_found"))
    elif len(res) > 200:
        await msg.finish(msg.locale.t("chunithm.message.too_much", length=len(res)))
    else:
        search_result = msg.locale.t("chunithm.message.search", keyword=name) + "\n"
        for music in sorted(res, key=lambda i: int(i['id'])):
            search_result += f"{music['id']}\u200B. {music['title']}\n"
        if len(res) <= 10:
            await msg.finish([Plain(search_result.strip())])
        else:
            img = await msgchain2image([Plain(search_result)])
            await msg.finish([BImage(img)])


@chu.command('id <id> [<diff>] {{chunithm.help.id}}')
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
        await msg.finish(msg.locale.t("chunithm.message.music_not_found"))

    if diff:
        diff_index = get_diff(diff)
        if not diff_index or (len(music['ds']) == 4 and diff_index == 4):
            await msg.finish(msg.locale.t("chunithm.message.chart_not_found"))
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


@chu.command('random [<diff+level>] {{chunithm.help.random}}')
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
            await msg.finish(msg.locale.t("chunithm.message.music_not_found"))
        else:
            music = music_data.random()
            await msg.finish(await get_info(msg, music, Plain(f"{'/'.join(str(ds) for ds in music.ds)}")))
    except (ValueError, TypeError):
        await msg.finish(msg.locale.t("chunithm.message.random.error"))
