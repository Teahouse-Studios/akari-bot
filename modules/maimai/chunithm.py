from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, Image as BImage
from core.component import module
from core.types import Param
from core.utils.func import is_int
from core.utils.image import msgchain2image
from .libraries.chunithm_apidata import get_info, update_cover
from .libraries.chunithm_best30 import generate as generate_b30
from .libraries.chunithm_music import TotalList
from .libraries.chunithm_utils import *
from .libraries.divingfish_oauth import bind_account, unbind_account
from .libraries.lxns_oauth import bind_account as bind_lx_account, unbind_account as unbind_lx_account
from .libraries.source import (
    GAME_CHUNITHM,
    SOURCE_DIVING_FISH,
    SOURCE_LXNS,
    pick_source,
    switch_source,
)

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
async def _(msg: Bot.MessageSession, constant: float, constant_max: float | None = None, page: str | None = None):
    result_set = []
    if constant <= 0:
        await msg.finish(I18NContext("maimai.message.level_invalid"))
    elif constant_max:
        if constant > constant_max:
            data = (await total_list.get()).filter(ds=(constant_max, constant))
            msg_chain = MessageChain.assign(
                I18NContext(
                    "maimai.message.base.range", constant=round(constant_max, 1), constant_max=round(constant, 1)
                )
            )
        else:
            data = (await total_list.get()).filter(ds=(constant, constant_max))
            msg_chain = MessageChain.assign(
                I18NContext(
                    "maimai.message.base.range", constant=round(constant, 1), constant_max=round(constant_max, 1)
                )
            )
    else:
        data = (await total_list.get()).filter(ds=constant)
        msg_chain = MessageChain.assign(I18NContext("maimai.message.base", constant=round(constant, 1)))

    for music in sorted(data, key=lambda i: int(i.get("id", 0))):
        for i in music.diff:
            result_set.append(
                (
                    music.get("id", ""),
                    music.get("title", ""),
                    music.get("ds", [])[i] if i < len(music.get("ds", [])) else 0,
                    diff_list[i],
                    music.get("level", [])[i] if i < len(music.get("level", [])) else "",
                )
            )

    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and is_int(page) else 1
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
async def _(msg: Bot.MessageSession, level: str, page: str | None = None):
    result_set = []
    data = (await total_list.get()).filter(level=level)
    for music in sorted(data, key=lambda i: int(i.get("id", 0))):
        for i in music.diff:
            result_set.append(
                (
                    music.get("id", ""),
                    music.get("title", ""),
                    music.get("ds", [])[i] if i < len(music.get("ds", [])) else 0,
                    diff_list[i],
                    music.get("level", [])[i] if i < len(music.get("level", [])) else "",
                )
            )
    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and is_int(page) else 1
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
async def _(msg: Bot.MessageSession, keyword: str, page: str | None = None):
    name = keyword.strip()
    result_set = []
    data = (await total_list.get()).filter(title_search=name)
    if len(data) == 0:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    for music in sorted(data, key=lambda i: int(i.get("id", 0))):
        result_set.append((music.get("id", ""), music.get("title", "")))
    total_pages = (len(result_set) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(min(int(page), total_pages), 1) if page and is_int(page) else 1
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


@chu.command("chart <song> {{I18N:maimai.help.chart}}")
async def _(msg: Bot.MessageSession, song: str):
    if is_int(song):
        music = (await total_list.get()).by_id(song)
    elif song[:2].lower() == "id":
        sid = song[2:]
        music = (await total_list.get()).by_id(sid)
    else:
        music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    msg_chain = MessageChain.assign()
    music_ds = music.get("ds", [])
    music_charts = music.get("charts", [])
    music_level = music.get("level", [])
    if len(music_ds) == 1:
        chart = music_charts[0] if music_charts else {}
        notes = chart.get("notes", [0, 0, 0, 0, 0])
        ds = music_ds[0]
        level = music_level[0] if music_level else ""
        msg_chain.append(
            I18NContext(
                "chunithm.message.chart",
                diff="World's End",
                level=level,
                ds="☆" * ds,
                tap=notes[0] if len(notes) > 0 else 0,
                hold=notes[1] if len(notes) > 1 else 0,
                slide=notes[2] if len(notes) > 2 else 0,
                air=notes[3] if len(notes) > 3 else 0,
                flick=notes[4] if len(notes) > 4 else 0,
                charter=chart.get("charter", ""),
            )
        )
    else:
        for _diff, ds in enumerate(music_ds):
            chart = music_charts[_diff] if _diff < len(music_charts) else {}
            notes = chart.get("notes", [0, 0, 0, 0, 0])
            level = music_level[_diff] if _diff < len(music_level) else ""
            msg_chain.append(
                I18NContext(
                    "chunithm.message.chart",
                    diff=diff_list[_diff],
                    level=level,
                    ds=ds,
                    tap=notes[0] if len(notes) > 0 else 0,
                    hold=notes[1] if len(notes) > 1 else 0,
                    slide=notes[2] if len(notes) > 2 else 0,
                    air=notes[3] if len(notes) > 3 else 0,
                    flick=notes[4] if len(notes) > 4 else 0,
                    charter=chart.get("charter", ""),
                )
            )
    await msg.finish(await get_info(music, msg_chain))


@chu.command("id <id> {{I18N:maimai.help.id}}")
@chu.command("song <song> {{I18N:maimai.help.song}}")
async def _(msg: Bot.MessageSession, song: str, sid: Param("<id>", str) = None):
    if sid:
        music = (await total_list.get()).by_id(sid)
    else:
        if is_int(song):
            music = (await total_list.get()).by_id(song)
        elif song[:2].lower() == "id":
            sid = song[2:]
            music = (await total_list.get()).by_id(sid)
        else:
            music = (await total_list.get()).by_title(song)

    if not music:
        await msg.finish(I18NContext("maimai.message.music_not_found"))

    msg_chain = MessageChain.assign()
    music_ds = music.get("ds", [])
    basic_info = music.get("basic_info", {})
    if len(music_ds) == 6:
        msg_chain.append(
            I18NContext(
                "chunithm.message.song.worlds_end",
                artist=basic_info.get("artist", ""),
                genre=basic_info.get("genre", ""),
                bpm=basic_info.get("bpm", 0),
                version=basic_info.get("from", ""),
            )
        )
    else:
        msg_chain.append(
            I18NContext(
                "chunithm.message.song",
                artist=basic_info.get("artist", ""),
                genre=basic_info.get("genre", ""),
                bpm=basic_info.get("bpm", 0),
                version=basic_info.get("from", ""),
                level="/".join((str(ds) for ds in music_ds)),
            )
        )
    await msg.finish(await get_info(music, msg_chain))


@chu.command("random [<diff+level>] {{I18N:maimai.help.random}}")
async def _(msg: Bot.MessageSession, condit: Param("<diff+level>", str) = ""):
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
                diffs = MessageChain.assign(Plain(f"{'/'.join(str(ds) for ds in music.ds)}"))
                await msg.finish(await get_info(music, diffs))
            else:
                raise ValueError
        else:
            if diff == "":
                music_data = (await total_list.get()).filter(level=level)
            else:
                music_data = (await total_list.get()).filter(level=level, diff=[get_diff(diff)])

        if len(music_data) == 0:
            await msg.finish(I18NContext("maimai.message.music_not_found"))
        else:
            music = music_data.random()
            diffs = MessageChain.assign(Plain(f"{'/'.join(str(ds) for ds in music.ds)}"))
            await msg.finish(await get_info(music, diffs))
    except (ValueError, TypeError):
        await msg.finish(I18NContext("maimai.message.random.failed"))


@chu.command("bind df {{I18N:maimai.help.bind.df}}")
async def _(msg: Bot.MessageSession):
    await bind_account(msg)


@chu.command("unbind df {{I18N:maimai.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await unbind_account(msg)


@chu.command("bind lx [<auth_code>] {{I18N:maimai.help.bind.lx}}")
async def _(msg: Bot.MessageSession, auth_code: str | None = None):
    await bind_lx_account(msg, auth_code, ActionText(f"{msg.session_info.prefixes[0]}chunithm bind lx "))


@chu.command("unbind lx {{I18N:maimai.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await unbind_lx_account(msg)


@chu.command("switch {{I18N:chunithm.help.switch}}")
async def _(msg: Bot.MessageSession):
    prefix = msg.session_info.prefixes[0]
    await switch_source(
        msg,
        GAME_CHUNITHM,
        {
            SOURCE_DIVING_FISH: f"{prefix}chunithm bind df",
            SOURCE_LXNS: f"{prefix}chunithm bind lx",
        },
    )


@chu.command("b30 [<user>] {{I18N:chunithm.help.b30}}")
async def _(msg: Bot.MessageSession, user: str | None = None):
    username = ""
    friend_code = ""
    if pick_source(msg, GAME_CHUNITHM) == SOURCE_LXNS:
        # 落雪的查询对象是好友码；不填参数时由令牌认出账号。
        if user and not is_int(user):
            await msg.finish(I18NContext("maimai.message.friend_code_invalid"))
        token = None if user else await get_lxns_prober_bind_info(msg)
        friend_code = user or ""
        source = "Lxns"
    else:
        # 填了用户名便查这个玩家，无需绑定。
        token = None if user else await get_diving_prober_bind_info(msg)
        username = user or ""
        source = "Diving-Fish"
    img = await generate_b30(msg, token, source, username=username, friend_code=friend_code, use_cache=not user)
    if img:
        await msg.finish(BImage(img))


@chu.command("update [--no-cover]", required_superuser=True)
async def _(msg: Bot.MessageSession, no_cover: bool = False):
    if no_cover:
        actions = await total_list.update()
    else:
        actions = await update_cover() and await total_list.update()
    if actions:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))
