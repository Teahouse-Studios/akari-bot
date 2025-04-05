from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.utils.image import msgchain2image
from core.utils.text import isint
from modules.maimai.database.models import DivingProberBindInfo
from .libraries.chunithm_apidata import get_info, get_record
from .libraries.chunithm_mapping import diff_list
from .libraries.chunithm_music import TotalList
from .libraries.chunithm_utils import generate_best30_text, get_diff, SONGS_PER_PAGE

total_list = TotalList()

chu = module(
    "chunithm",
    developers=["DoroWolf"],
    doc=True,
    alias="chu",
    support_languages=["zh_cn"],
    desc="{chunithm.help.desc}",
)


@chu.command(
    "base <constant> [<constant_max>] [-p <page>] {{maimai.help.base}}",
    options_desc={"-p": "{maimai.help.option.p}"},
)
async def _(msg: Bot.MessageSession, constant: float, constant_max: float = None):
    result_set = []
    if constant <= 0:
        await msg.finish(msg.locale.t("maimai.message.level_invalid"))
    elif constant_max:
        if constant > constant_max:
            data = (await total_list.get()).filter(ds=(constant_max, constant))
            s = (
                msg.locale.t(
                    "maimai.message.base.range",
                    constant=round(constant_max, 1),
                    constant_max=round(constant, 1),
                )
                + "\n"
            )
        else:
            data = (await total_list.get()).filter(ds=(constant, constant_max))
            s = (
                msg.locale.t(
                    "maimai.message.base.range",
                    constant=round(constant, 1),
                    constant_max=round(constant_max, 1),
                )
                + "\n"
            )
    else:
        data = (await total_list.get()).filter(ds=constant)
        s = msg.locale.t("maimai.message.base", constant=round(constant, 1)) + "\n"

    for music in sorted(data, key=lambda i: int(i["id"])):
        for i in music.diff:
            result_set.append(
                (
                    music["id"],
                    music["title"],
                    music["ds"][i],
                    diff_list[i],
                    music["level"][i],
                )
            )

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    get_page = msg.parsed_msg.get("-p", False)
    page = (
        max(min(int(get_page["<page>"]), total_pages), 1)
        if get_page and isint(get_page["<page>"])
        else 1
    )
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]} - {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"
    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("maimai.message.pages", page=page, total_pages=total_pages)
        imgs = await msgchain2image([Plain(s)])
        if imgs:
            imgchain = []
            for img in imgs:
                imgchain.append(BImage(img))
            await msg.finish(imgchain)
        else:
            await msg.finish(s)


@chu.command(
    "level <level> [-p <page>] {{maimai.help.level}}",
    options_desc={"-p": "{maimai.help.option.p}"},
)
async def _(msg: Bot.MessageSession, level: str):
    result_set = []
    data = (await total_list.get()).filter(level=level)
    for music in sorted(data, key=lambda i: int(i["id"])):
        for i in music.diff:
            result_set.append(
                (
                    music["id"],
                    music["title"],
                    music["ds"][i],
                    diff_list[i],
                    music["level"][i],
                )
            )
    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    get_page = msg.parsed_msg.get("-p", False)
    page = (
        max(min(int(get_page["<page>"]), total_pages), 1)
        if get_page and isint(get_page["<page>"])
        else 1
    )
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    s = msg.locale.t("maimai.message.level", level=level) + "\n"
    for elem in result_set[start_index:end_index]:
        s += f"{elem[0]} - {elem[1]} {elem[3]} {elem[4]} ({elem[2]})\n"

    if len(result_set) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(s.strip())
    else:
        s += msg.locale.t("maimai.message.pages", page=page, total_pages=total_pages)
        imgs = await msgchain2image([Plain(s)])
        if imgs:
            imgchain = []
            for img in imgs:
                imgchain.append(BImage(img))
            await msg.finish(imgchain)
        else:
            await msg.finish(s)


@chu.command("search <keyword> [-p <page>] {{maimai.help.search}}")
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    result_set = []
    data = (await total_list.get()).filter(title_search=name)
    if len(data) == 0:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))
    else:
        for music in sorted(data, key=lambda i: int(i["id"])):
            result_set.append((music["id"], music["title"]))
        total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
        get_page = msg.parsed_msg.get("-p", False)
        page = (
            max(min(int(get_page["<page>"]), total_pages), 1)
            if get_page and isint(get_page["<page>"])
            else 1
        )
        start_index = (page - 1) * SONGS_PER_PAGE
        end_index = page * SONGS_PER_PAGE

        s = msg.locale.t("maimai.message.search", keyword=name) + "\n"
        for elem in result_set[start_index:end_index]:
            s += f"{elem[0]} - {elem[1]}\n"
        if len(data) <= SONGS_PER_PAGE:
            await msg.finish(s.strip())
        else:
            s += msg.locale.t(
                "maimai.message.pages", page=page, total_pages=total_pages
            )
            imgs = await msgchain2image([Plain(s)])
            if imgs:
                imgchain = []
                for img in imgs:
                    imgchain.append(BImage(img))
                await msg.finish(imgchain)


@chu.command("b30 [<username>] {{chunithm.help.b30}}")
async def _(msg: Bot.MessageSession, username: str = None):
    if not username:
        if msg.target.sender_from == "QQ":
            payload = {"qq": msg.session.sender}
        else:
            bind_info = await DivingProberBindInfo.get_or_none(sender_id=msg.target.sender_id)
            if not bind_info:
                await msg.finish(
                    msg.locale.t("chunithm.message.user_unbound", prefix=msg.prefixes[0])
                )
            username = bind_info.username
            payload = {"username": username}
        use_cache = True
    else:
        payload = {"username": username}
        use_cache = False

    imgs = await generate_best30_text(msg, payload, use_cache)
    imgchain = []
    for img in imgs:
        imgchain.append(BImage(img))
    await msg.finish(imgchain)


@chu.command("chart <song> {{maimai.help.chart}}")
async def _(msg: Bot.MessageSession, song: str):
    if song[:2].lower() == "id":
        sid = song[2:]
        music = (await total_list.get()).by_id(sid)
    else:
        music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    res = []
    if len(music["ds"]) == 6:
        chart = music["charts"][5]
        ds = music["ds"][5]
        level = music["level"][5]
        res.append(
            msg.locale.t(
                "chunithm.message.chart",
                diff="World's End",
                level=level,
                ds=ds,
                combo=chart["combo"],
                charter=chart["charter"],
            )
        )
    else:
        for _diff, ds in enumerate(music["ds"]):
            chart = music["charts"][_diff]
            level = music["level"][_diff]
            res.append(
                msg.locale.t(
                    "chunithm.message.chart",
                    diff=diff_list[_diff],
                    level=level,
                    ds=ds,
                    combo=chart["combo"],
                    charter=chart["charter"],
                )
            )
    await msg.finish(await get_info(music, Plain("\n".join(res))))


@chu.command(
    "id <id> {{maimai.help.id}}",
)
@chu.command("song <song> {{maimai.help.song}}")
async def _(msg: Bot.MessageSession, song: str):
    if "<id>" in msg.parsed_msg:
        sid = msg.parsed_msg["<id>"]
        music = (await total_list.get()).by_id(sid)
    elif song[:2].lower() == "id":
        sid = song[2:]
        music = (await total_list.get()).by_id(sid)
    else:
        music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(msg.locale.t("maimai.message.music_not_found"))

    if len(music["ds"]) == 6:
        res = msg.locale.t(
            "chunithm.message.song.worlds_end",
            artist=music["basic_info"]["artist"],
            genre=music["basic_info"]["genre"],
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
        )
    else:
        res = msg.locale.t(
            "chunithm.message.song",
            artist=music["basic_info"]["artist"],
            genre=music["basic_info"]["genre"],
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
            level="/".join((str(ds) for ds in music["ds"])),
        )
    await msg.finish(await get_info(music, Plain(res)))


@chu.command("random [<diff+level>] {{maimai.help.random}}")
async def _(msg: Bot.MessageSession):
    condit = msg.parsed_msg.get("<diff+level>", "")
    level = ""
    diff = ""
    try:
        for char in condit:
            if isint(char) or char == "+":
                level += char
            else:
                diff += char

        if level == "":
            if diff == "":
                music = (await total_list.get()).random()
                await msg.finish(
                    await get_info(
                        music, Plain(f"{"/".join(str(ds) for ds in music.ds)}")
                    )
                )
            else:
                raise ValueError
        else:
            if diff == "":
                music_data = (await total_list.get()).filter(level=level)
            else:
                music_data = (await total_list.get()).filter(
                    level=level, diff=[get_diff(diff)]
                )

        if len(music_data) == 0:
            await msg.finish(msg.locale.t("maimai.message.music_not_found"))
        else:
            music = music_data.random()
            await msg.finish(
                await get_info(music, Plain(f"{"/".join(str(ds) for ds in music.ds)}"))
            )
    except (ValueError, TypeError):
        await msg.finish(msg.locale.t("maimai.message.random.failed"))


@chu.command("bind <username> {{maimai.help.bind}}", exclude_from=["QQ|Private", "QQ|Group"])
async def _(msg: Bot.MessageSession, username: str):
    await get_record(msg, {"username": username}, use_cache=False)
    await DivingProberBindInfo.set_bind_info(sender_id=msg.target.sender_id, username=username)
    await msg.finish(msg.locale.t("maimai.message.bind.success") + username)


@chu.command("unbind {{maimai.help.unbind}}", exclude_from=["QQ|Private", "QQ|Group"])
async def _(msg: Bot.MessageSession):
    await DivingProberBindInfo.remove_bind_info(sender_id=msg.target.sender_id)
    await msg.finish(msg.locale.t("maimai.message.unbind.success"))
