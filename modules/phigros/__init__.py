import shutil

from core.builtins.bot import Bot
from core.builtins.message.internal import Image, I18NContext
from core.component import module
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download
from modules.phigros.database.models import PhigrosBindInfo
from .game_record import parse_game_record
from .genb30 import drawb30
from .update import update_assets, p_headers

phi = module(
    "phigros",
    developers=["Mivik", "OasisAkari", "DoroWolf"],
    desc="{I18N:phigros.help.desc}",
    alias=["p", "pgr", "phi"],
    doc=True,
)


@phi.command("bind <sessiontoken> {{I18N:phigros.help.bind}}")
async def _(msg: Bot.MessageSession, sessiontoken: str):
    if msg.session_info.target_from in [
        "Discord|Channel",
        "KOOK|Group",
        "Matrix|Room",
        "QQ|Group",
        "QQBot|Group",
        "QQBot|Guild",
        "Telegram|Group",
        "Telegram|Supergroup",
    ]:
        await msg.send_message(I18NContext("phigros.message.bind.warning"), quote=False)
        deleted = await msg.delete()
        if not deleted:
            await msg.send_message(I18NContext("phigros.message.bind.delete_failed"), quote=False)
    headers = p_headers.copy()
    headers["X-LC-Session"] = sessiontoken
    get_user_info = await get_url(
        "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/users/me",
        headers=headers,
        fmt="json",
    )
    if get_user_info:
        username = get_user_info.get("nickname", "Guest")
        await PhigrosBindInfo.set_bind_info(sender_id=msg.session_info.sender_id, session_token=sessiontoken,
                                            username=username)
        await msg.send_message(I18NContext("phigros.message.bind.success", username=username), quote=False)
    else:
        await msg.send_message(I18NContext("phigros.message.bind.failed"))


@phi.command("unbind {{I18N:phigros.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await PhigrosBindInfo.remove_bind_info(sender_id=msg.session_info.sender_id)
    await msg.finish(I18NContext("phigros.message.unbind.success"))


@phi.command("b30 {{I18N:phigros.help.b30}}")
async def _(msg: Bot.MessageSession):
    bind_info = await PhigrosBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        await msg.finish(I18NContext("phigros.message.user_unbound", prefix=msg.session_info.prefixes[0]))
    else:
        headers = p_headers.copy()
        headers["X-LC-Session"] = bind_info.session_token
        get_save_url = await get_url(
            "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/classes/_GameSave",
            headers=headers,
            fmt="json",
        )
        save_url = get_save_url["results"][0]["gameFile"]["url"]
        dl = await download(save_url)
        rd_path = random_cache_path()
        shutil.unpack_archive(dl, rd_path)
        game_records = parse_game_record(rd_path)
        Logger.debug(str(game_records))
        result = []

        for song_id, song_data in game_records.items():
            name = song_data["name"]
            for diff, info in song_data["diff"].items():
                result.append((song_id, diff, name, info))

        result.sort(key=lambda x: x[3]["rks"], reverse=True)

        phi_list = [s for s in result if s[3]["score"] == 1000000]

        p3_data = sorted(phi_list, key=lambda x: x[3]["rks"], reverse=True)[:3]
        b27_data = result[:27]

        all_rks = [i[3]["rks"] for i in (p3_data + b27_data)]
        if len(all_rks) < 30:
            all_rks += [0] * (30 - len(all_rks))
        avg_acc = round(sum(all_rks) / len(all_rks), 2)

        Logger.debug(f"P3 Data: {p3_data}")
        Logger.debug(f"B27 Data: {b27_data}")

        await msg.finish(Image(drawb30(bind_info.username, avg_acc, p3_data, b27_data)))


@phi.command("update [--no-illus]", required_superuser=True)
async def _(msg: Bot.MessageSession):
    if await update_assets(not msg.parsed_msg.get("--no-illus", False)):
        await msg.finish(I18NContext("message.success"))
    else:
        await msg.finish(I18NContext("message.failed"))
