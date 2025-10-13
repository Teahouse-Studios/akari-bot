from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext
from core.component import module
from core.utils.image import msgchain2image
from core.utils.message import is_int
from .database.models import DivingProberBindInfo
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
    desc="{I18N:chunithm.help.desc}",
)


@chu.command(
    "base <constant> [<constant_max>] [-p <page>] {{I18N:maimai.help.base}}",
    options_desc={"-p": "{I18N:maimai.help.option.p}"},
)
async def _(msg: Bot.MessageSession, constant: float, constant_max: float = None):
    result_set = []
    if constant <= 0:
        await msg.finish(I18NContext("maimai.message.level_invalid"))
    elif constant_max:
        if constant > constant_max:
            data = (await total_list.get()).filter(ds=(constant_max, constant))
            msg_chain = MessageChain.assign(I18NContext(
                "maimai.message.base.range",
                constant=round(constant_max, 1),
                constant_max=round(constant, 1))
            )
        else:
            data = (await total_list.get()).filter(ds=(constant, constant_max))
            msg_chain = MessageChain.assign(I18NContext(
                "maimai.message.base.range",
                constant=round(constant, 1),
                constant_max=round(constant_max, 1)
            ))
    else:
        data = (await total_list.get()).filter(ds=constant)
        msg_chain = MessageChain.assign(I18NContext("maimai.message.base", constant=round(constant, 1)))

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
        if get_page and is_int(get_page["<page>"])
        else 1
    )
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    for elem in result_set[start_index:end_index]:
        msg_chain.append(Plain(f"{elem[0]} - {elem[1]} {elem[3]} {elem[4]} ({elem[2]})"))
    if len(result_set) == 0:
        await msg.finish(I18NContext("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(msg_chain)
    else:
        msg_chain.append(I18NContext("maimai.message.pages", page=page, total_pages=total_pages))
        imgs = await msgchain2image(msg_chain, msg)
        if imgs:
            await msg.finish(imgs)
        else:
            await msg.finish(msg_chain)


@chu.command(
    "level <level> [-p <page>] {{I18N:maimai.help.level}}",
    options_desc={"-p": "{I18N:maimai.help.option.p}"},
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
        if get_page and is_int(get_page["<page>"])
        else 1
    )
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    msg_chain = MessageChain.assign(I18NContext("maimai.message.level", level=level))
    for elem in result_set[start_index:end_index]:
        msg_chain.append(Plain(f"{elem[0]} - {elem[1]} {elem[3]} {elem[4]} ({elem[2]})"))

    if len(result_set) == 0:
        await msg.finish(I18NContext("maimai.message.music_not_found"))
    elif len(result_set) <= SONGS_PER_PAGE:
        await msg.finish(msg_chain)
    else:
        msg_chain.append(I18NContext("maimai.message.pages", page=page, total_pages=total_pages))
        imgs = await msgchain2image(msg_chain, msg)
        if imgs:
            await msg.finish(imgs)
        else:
            await msg.finish(msg_chain)


@chu.command("search <keyword> [-p <page>] {{I18N:maimai.help.search}}")
async def _(msg: Bot.MessageSession, keyword: str):
    name = keyword.strip()
    result_set = []
    data = (await total_list.get()).filter(title_search=name)
    if len(data) == 0:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    for music in sorted(data, key=lambda i: int(i["id"])):
        result_set.append((music["id"], music["title"]))
    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    get_page = msg.parsed_msg.get("-p", False)
    page = (
        max(min(int(get_page["<page>"]), total_pages), 1)
        if get_page and is_int(get_page["<page>"])
        else 1
    )
    start_index = (page - 1) * SONGS_PER_PAGE
    end_index = page * SONGS_PER_PAGE

    msg_chain = MessageChain.assign(I18NContext("maimai.message.search", keyword=name))
    for elem in result_set[start_index:end_index]:
        msg_chain.append(Plain(f"{elem[0]} - {elem[1]}"))
    if len(data) <= SONGS_PER_PAGE:
        await msg.finish(msg_chain)
    else:
        msg_chain.append(I18NContext("maimai.message.pages", page=page, total_pages=total_pages))
        imgs = await msgchain2image(msg_chain, msg)
        if imgs:
            await msg.finish(imgs)
        else:
            await msg.finish(msg_chain)


@chu.command("b30 [<username>] {{I18N:chunithm.help.b30}}")
async def _(msg: Bot.MessageSession, username: str = None):
    if not username:
        if msg.session_info.sender_from == "QQ":
            payload = {"qq": msg.session_info.get_common_sender_id()}
        else:
            bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
            if not bind_info:
                await msg.finish(
                    msg.session_info.locale.t("chunithm.message.user_unbound", prefix=msg.session_info.prefixes[0])
                )
            username = bind_info.username
            payload = {"username": username}
        use_cache = True
    else:
        payload = {"username": username}
        use_cache = False

    imgs = await generate_best30_text(msg, payload, use_cache)
    if imgs:
        await msg.finish(imgs)


@chu.command("chart <song> {{I18N:maimai.help.chart}}")
async def _(msg: Bot.MessageSession, song: str):
    if song[:2].lower() == "id":
        sid = song[2:]
        music = (await total_list.get()).by_id(sid)
    else:
        music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    msg_chain = MessageChain.assign()
    if len(music["ds"]) == 6:
        chart = music["charts"][5]
        ds = music["ds"][5]
        level = music["level"][5]
        msg_chain.append(I18NContext(
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
            msg_chain.append(I18NContext(
                "chunithm.message.chart",
                diff=diff_list[_diff],
                level=level,
                ds=ds,
                combo=chart["combo"],
                charter=chart["charter"],
            )
            )
    await msg.finish(await get_info(music, msg_chain))


@chu.command("id <id> {{I18N:maimai.help.id}}")
@chu.command("song <song> {{I18N:maimai.help.song}}")
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
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    msg_chain = MessageChain.assign()
    if len(music["ds"]) == 6:
        msg_chain.append(I18NContext(
            "chunithm.message.song.worlds_end",
            artist=music["basic_info"]["artist"],
            genre=music["basic_info"]["genre"],
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
        ))
    else:
        msg_chain.append(I18NContext(
            "chunithm.message.song",
            artist=music["basic_info"]["artist"],
            genre=music["basic_info"]["genre"],
            bpm=music["basic_info"]["bpm"],
            version=music["basic_info"]["from"],
            level="/".join((str(ds) for ds in music["ds"])),
        ))
    await msg.finish(await get_info(music, msg_chain))


@chu.command("random [<diff+level>] {{I18N:maimai.help.random}}")
async def _(msg: Bot.MessageSession):
    condit = msg.parsed_msg.get("<diff+level>", "")
    level = ""
    diff = ""
    try:
        for char in condit:
            if is_int(char) or char == "+":
                level += char
            else:
                diff += char

        if level == "":
            if diff == "":
                music = (await total_list.get()).random()
                diffs = MessageChain.assign(Plain(f"{"/".join(str(ds) for ds in music.ds)}"))
                await msg.finish(await get_info(music, diffs))
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
            await msg.finish(I18NContext("maimai.message.music_not_found"))
        else:
            music = music_data.random()
            diffs = MessageChain.assign(Plain(f"{"/".join(str(ds) for ds in music.ds)}"))
            await msg.finish(await get_info(music, diffs))
    except (ValueError, TypeError):
        await msg.finish(I18NContext("maimai.message.random.failed"))


@chu.command("bind <username> {{I18N:maimai.help.bind}}", exclude_from=["QQ|Private", "QQ|Group"])
async def _(msg: Bot.MessageSession, username: str):
    await get_record(msg, {"username": username}, use_cache=False)
    await DivingProberBindInfo.set_bind_info(sender_id=msg.session_info.sender_id, username=username)
    await msg.finish(msg.session_info.locale.t("maimai.message.bind.success") + username)


@chu.command("unbind {{I18N:maimai.help.unbind}}", exclude_from=["QQ|Private", "QQ|Group"])
async def _(msg: Bot.MessageSession):
    await DivingProberBindInfo.remove_bind_info(sender_id=msg.session_info.sender_id)
    await msg.finish(I18NContext("maimai.message.unbind.success"))
