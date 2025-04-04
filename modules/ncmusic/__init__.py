from core.builtins import Bot, I18NContext, Image, Url
from core.component import module
from core.config import Config
from core.constants.exceptions import ConfigValueError
from core.utils.http import get_url
from core.utils.image_table import image_table_render, ImageTable
from core.utils.text import isint

API = Config("ncmusic_api", cfg_type=str, secret=True, table_name="module_ncmusic")
SEARCH_LIMIT = 10

ncmusic = module(
    "ncmusic",
    developers=["bugungu"],
    desc="{ncmusic.help.desc}",
    doc=True,
    support_languages=["zh_cn"],
)


@ncmusic.command(
    "search [--legacy] <keyword> {{ncmusic.help.search}}",
    options_desc={"--legacy": "{help.option.legacy}"},
)
async def _(msg: Bot.MessageSession, keyword: str):
    if not API:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    url = f"{API}/search?keywords={keyword}"
    result = await get_url(url, 200, fmt="json")
    song_count = result["result"]["songCount"]
    legacy = True

    if song_count == 0:
        await msg.finish(msg.locale.t("ncmusic.message.search.not_found"))

    songs = result["result"]["songs"][:SEARCH_LIMIT]

    if not msg.parsed_msg.get("--legacy", False) and msg.Feature.image:

        send_msg = [I18NContext("ncmusic.message.search.result")]
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
                msg.locale.t("ncmusic.message.search.table.header.id"),
                msg.locale.t("ncmusic.message.search.table.header.name"),
                msg.locale.t("ncmusic.message.search.table.header.artists"),
                msg.locale.t("ncmusic.message.search.table.header.album"),
                "ID",
            ],
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
            query = await msg.wait_confirm(send_msg, delete=False)
            if query:
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
                    await msg.finish(
                        msg.locale.t("mod_dl.message.invalid.out_of_range")
                    )
                else:
                    sid = result["result"]["songs"][query - 1]["id"]
            else:
                await msg.finish(
                    msg.locale.t("ncmusic.message.search.invalid.non_digital")
                )

        await info(msg, sid)

    if legacy:
        send_msg = msg.locale.t("ncmusic.message.search.result") + "\n"

        for i, song in enumerate(songs, start=1):
            send_msg += f"{i} - {song["name"]}"
            if "transNames" in song:
                send_msg += f"（{" / ".join(song["transNames"])}）"
            send_msg += f"——{" / ".join(artist["name"] for artist in song["artists"])}"
            if song["album"]["name"]:
                send_msg += f"《{song["album"]["name"]}》"
            if "transNames" in song["album"]:
                send_msg += f"（{" / ".join(song["album"]["transNames"])}）"
            send_msg += f"（{song["id"]}）\n"

        if song_count > SEARCH_LIMIT:
            song_count = SEARCH_LIMIT
            send_msg += msg.locale.t("message.collapse", amount=SEARCH_LIMIT)

        if song_count == 1:
            send_msg += "\n" + msg.locale.t("ncmusic.message.search.confirm")
            query = await msg.wait_confirm(send_msg, delete=False)
            if query:
                sid = result["result"]["songs"][0]["id"]
            else:
                await msg.finish()
        else:
            send_msg += "\n" + msg.locale.t("ncmusic.message.search.prompt")
            query = await msg.wait_reply(send_msg)
            query = query.as_display(text_only=True)

            if isint(query):
                query = int(query)
                if query > song_count:
                    await msg.finish(
                        msg.locale.t("mod_dl.message.invalid.out_of_range")
                    )
                else:
                    sid = result["result"]["songs"][query - 1]["id"]
            else:
                await msg.finish(
                    msg.locale.t("ncmusic.message.search.invalid.non_digital")
                )

        if msg.target.client_name == "QQ" and Config("ncmusic_enable_card", False):
            await msg.finish(f"[CQ:music,type=163,id={sid}]", quote=False)
        else:
            await info(msg, sid)


@ncmusic.command("<sid> {{ncmusic.help}}", available_for=["QQ|Group", "QQ|Private"])
async def _(msg: Bot.MessageSession, sid: int):
    if Config("ncmusic_enable_card", False, table_name="module_ncmusic"):
        await msg.finish(f"[CQ:music,type=163,id={sid}]", quote=False)
    else:
        await info(msg, sid)


@ncmusic.command("info <sid> {{ncmusic.help.info}}")
async def _(msg: Bot.MessageSession, sid: int):
    await info(msg, sid)


async def info(msg: Bot.MessageSession, sid: int):
    if not API:
        raise ConfigValueError("[I18N:error.config.secret.not_found]")
    url = f"{API}/song/detail?ids={sid}"
    result = await get_url(url, 200, fmt="json")

    if result["songs"]:
        info = result["songs"][0]
        artist = " / ".join([ar["name"] for ar in info["ar"]])
        song_url = f"https://music.163.com/#/song?id={info["id"]}"

        await msg.finish(
            [
                Image(info["al"]["picUrl"]),
                Url(song_url),
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
        await msg.finish(msg.locale.t("ncmusic.message.info.not_found"))
