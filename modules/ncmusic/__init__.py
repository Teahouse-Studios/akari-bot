from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Plain, I18NContext, Image, Url
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.utils.http import get_url
from core.utils.image_table import image_table_render, ImageTable
from core.utils.message import isint

enable_card = Config("ncmusic_enable_card", False, table_name="module_ncmusic")
API = Config("ncmusic_api", cfg_type=str, secret=True, table_name="module_ncmusic")
SEARCH_LIMIT = 10

ncmusic = module(
    "ncmusic",
    developers=["bugungu"],
    desc="{I18N:ncmusic.help.desc}",
    doc=True,
    support_languages=["zh_cn"],
)


@ncmusic.command(
    "search [--legacy] <keyword> {{I18N:ncmusic.help.search}}",
    options_desc={"--legacy": "{I18N:help.option.legacy}"},
)
async def _(msg: Bot.MessageSession, keyword: str):
    if not API:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")
    url = f"{API}/search?keywords={keyword}"
    result = await get_url(url, 200, fmt="json")
    song_count = result["result"]["songCount"]
    legacy = True

    if song_count == 0:
        await msg.finish(I18NContext("ncmusic.message.search.not_found"))

    songs = result["result"]["songs"][:SEARCH_LIMIT]

    send_msg = MessageChain.assign(I18NContext("ncmusic.message.search.result"))
    if not msg.parsed_msg.get("--legacy", False) and msg.session_info.support_image:

        data = [
            [
                str(i),
                song["name"]
                + (
                    f" ({" / ".join(song["transNames"])})"
                    if "transNames" in song
                    else ""
                ),
                f"{" / ".join(artist["name"] for artist in song["artists"])}",
                f"{song["album"]["name"]}"
                + (
                    f" ({" / ".join(song["album"]["transNames"])})"
                    if "transNames" in song["album"]
                    else ""
                ),
                f"{song["id"]}",
            ]
            for i, song in enumerate(songs, start=1)
        ]

        tables = ImageTable(
            data,
            [
                "{I18N:ncmusic.message.search.table.header.id}",
                "{I18N:ncmusic.message.search.table.header.name}",
                "{I18N:ncmusic.message.search.table.header.artists}",
                "{I18N:ncmusic.message.search.table.header.album}",
                "ID",
            ],
            msg.session_info
        )

        imgs = await image_table_render(tables)
        if imgs:
            legacy = False
            for img in imgs:
                send_msg.append(Image(img))
            if song_count > SEARCH_LIMIT:
                song_count = SEARCH_LIMIT
                send_msg.append(I18NContext("message.collapse", amount=SEARCH_LIMIT))

        if song_count == 1:
            send_msg.append(I18NContext("ncmusic.message.search.confirm"))
            if await msg.wait_confirm(send_msg, delete=False):
                sid = result["result"]["songs"][0]["id"]
            else:
                await msg.finish()

        else:
            send_msg.append(I18NContext("ncmusic.message.search.prompt"))
            query = await msg.wait_reply(send_msg)
            query = query.as_display(text_only=True)

            if isint(query):
                query = int(query)
                if not query or query > song_count:
                    await msg.finish(I18NContext("mod_dl.message.invalid.out_of_range"))
                else:
                    sid = result["result"]["songs"][query - 1]["id"]
            else:
                await msg.finish(I18NContext("ncmusic.message.search.invalid.non_digital"))

        await info(msg, sid)

    if legacy:

        for i, song in enumerate(songs, start=1):
            song_msg = f"{i} - {song["name"]}"
            if "transNames" in song:
                song_msg += f"（{" / ".join(song["transNames"])}）"
            song_msg += f"——{" / ".join(artist["name"] for artist in song["artists"])}"
            if song["album"]["name"]:
                song_msg += f"《{song["album"]["name"]}》"
            if "transNames" in song["album"]:
                song_msg += f"（{" / ".join(song["album"]["transNames"])}）"
            song_msg += f"（{song["id"]}）"
            send_msg.append(Plain(song_msg))

        if song_count > SEARCH_LIMIT:
            song_count = SEARCH_LIMIT
            send_msg.append(I18NContext("message.collapse", amount=SEARCH_LIMIT))

        if song_count == 1:
            send_msg.append(I18NContext("ncmusic.message.search.confirm"))
            if await msg.wait_confirm(send_msg, delete=False):
                sid = result["result"]["songs"][0]["id"]
            else:
                await msg.finish()
        else:
            send_msg.append(I18NContext("ncmusic.message.search.prompt"))
            query = await msg.wait_reply(send_msg)
            query = query.as_display(text_only=True)

            if isint(query):
                query = int(query)
                if query > song_count:
                    await msg.finish(I18NContext("mod_dl.message.invalid.out_of_range"))
                else:
                    sid = result["result"]["songs"][query - 1]["id"]
            else:
                await msg.finish(I18NContext("ncmusic.message.search.invalid.non_digital"))

        if msg.session_info.client_name == "QQ" and enable_card:
            await msg.finish(f"[CQ:music,type=163,id={sid}]", quote=False)
        else:
            await info(msg, sid)


@ncmusic.command("<sid> {{I18N:ncmusic.help}}", available_for=["QQ|Group", "QQ|Private"])
async def _(msg: Bot.MessageSession, sid: int):
    if enable_card:
        await msg.finish(f"[CQ:music,type=163,id={sid}]", quote=False)
    else:
        await info(msg, sid)


@ncmusic.command("info <sid> {{I18N:ncmusic.help.info}}")
async def _(msg: Bot.MessageSession, sid: int):
    await info(msg, sid)


async def info(msg: Bot.MessageSession, sid: int):
    if not API:
        raise ConfigValueError("{I18N:error.config.secret.not_found}")
    url = f"{API}/song/detail?ids={sid}"
    result = await get_url(url, 200, fmt="json")

    if result["songs"]:
        info = result["songs"][0]
        artist = " / ".join([ar["name"] for ar in info["ar"]])
        song_url = f"https://music.163.com/#/song?id={info["id"]}"

        await msg.finish(
            [
                Image(info["al"]["picUrl"]),
                Url(song_url, use_mm=False),
                I18NContext(
                    "ncmusic.message.info",
                    name=info["name"],
                    id=info["id"],
                    artists=artist,
                    album=info["al"]["name"],
                    album_id=info["al"]["id"],
                ),
            ]
        )
    else:
        await msg.finish(I18NContext("ncmusic.message.info.not_found"))
