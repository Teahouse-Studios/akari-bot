from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext, Image as BImage
from core.component import module
from core.utils.image import msgchain2image
from core.utils.func import is_int
from .database.models import DivingProberBindInfo, LxnsProberBindInfo
from .libraries.chunithm_apidata import get_info, get_record_df, get_record_lx, update_cover
from .libraries.chunithm_best30 import generate as generate_b30
from .libraries.chunithm_mapping import diff_list, default_source
from .libraries.chunithm_music import TotalList
from .libraries.chunithm_utils import *

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
    if len(music["ds"]) == 1:
        chart = music["charts"][0]
        ds = music["ds"][0]
        level = music["level"][0]
        msg_chain.append(I18NContext(
            "chunithm.message.chart",
            diff="World's End",
            level=level,
            ds="☆" * ds,
            tap=chart["notes"][0],
            hold=chart["notes"][1],
            slide=chart["notes"][2],
            air=chart["notes"][3],
            flick=chart["notes"][4],
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
                tap=chart["notes"][0],
                hold=chart["notes"][1],
                slide=chart["notes"][2],
                air=chart["notes"][3],
                flick=chart["notes"][4],
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


@chu.command("bind df <username> {{I18N:maimai.help.bind.df}}")
async def _(msg: Bot.MessageSession, username: str):
    if await get_record_df(msg, {"username": username}, use_cache=False):
        await DivingProberBindInfo.set_bind_info(sender_id=msg.session_info.sender_id, username=username)
        await msg.finish(msg.session_info.locale.t("maimai.message.bind.success") + username)


@chu.command("unbind df {{I18N:maimai.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await DivingProberBindInfo.remove_bind_info(sender_id=msg.session_info.sender_id)
    await msg.finish(I18NContext("maimai.message.unbind.success"))

if LX_DEVELOPER_TOKEN:
    @chu.command("switch {{I18N:chunithm.help.switch}}")
    async def _(msg: Bot.MessageSession):
        if msg.session_info.sender_info.sender_data.get("chunithum_record_source", default_source) == "lxns":
            await msg.session_info.sender_info.edit_sender_data("chunithum_record_source", "diving-fish")
            await msg.finish(I18NContext("maimai.message.switch.df"))
        else:
            await msg.session_info.sender_info.edit_sender_data("chunithum_record_source", "lxns")
            await msg.finish(I18NContext("maimai.message.switch.lx"))

    @chu.command("bind lx <friendcode> {{I18N:maimai.help.bind.lx}}")
    async def _(msg: Bot.MessageSession, friendcode: str):
        data = await get_record_lx(msg, friendcode, use_cache=False)
        if data:
            await LxnsProberBindInfo.set_bind_info(sender_id=msg.session_info.sender_id, friend_code=friendcode)
            await msg.finish(msg.session_info.locale.t("maimai.message.bind.success") + data["nickname"])

    @chu.command("unbind lx {{I18N:maimai.help.unbind}}")
    async def _(msg: Bot.MessageSession):
        await LxnsProberBindInfo.remove_bind_info(sender_id=msg.session_info.sender_id)
        await msg.finish(I18NContext("maimai.message.unbind.success"))


@chu.command("b30 {{I18N:chunithm.help.b30}}")
async def _(msg: Bot.MessageSession):
    if msg.session_info.sender_info.sender_data.get("chunithum_record_source", default_source) == "lxns":
        token = await get_lxns_prober_bind_info(msg)
        source = "Lxns"
    else:
        token = await get_diving_prober_bind_info(msg)
        source = "Diving-Fish"
    img = await generate_b30(msg, token, source)
    if img:
        await msg.finish(BImage(img))


@chu.command("update [--no-cover]", required_superuser=True)
async def _(msg: Bot.MessageSession):
    if msg.parsed_msg.get("--no-cover", False):
        actions = await total_list.update()
    else:
        actions = (
            await update_cover() and await total_list.update()
        )
    if actions:
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))
