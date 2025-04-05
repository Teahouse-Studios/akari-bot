import shutil
import traceback

from core.builtins import Bot, Image
from core.component import module
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.http import get_url, download
from modules.phigros.database.models import PhigrosBindInfo
from .game_record import parse_game_record
from .genb19 import drawb19
from .update import update_assets, p_headers

phi = module(
    "phigros",
    developers=["OasisAkari"],
    desc="{phigros.help.desc}",
    alias=["p", "pgr", "phi"],
    doc=True,
)


@phi.command("bind <sessiontoken> {{phigros.help.bind}}")
async def _(msg: Bot.MessageSession, sessiontoken: str):
    if msg.target.target_from in [
        "Discord|Channel",
        "KOOK|Group",
        "Matrix|Room",
        "QQ|Group",
        "QQ|Guild",
        "Telegram|Group",
        "Telegram|Supergroup",
    ]:
        await msg.send_message(
            msg.locale.t("phigros.message.bind.warning"), quote=False
        )
        deleted = await msg.delete()
        if not deleted:
            await msg.send_message(
                msg.locale.t("phigros.message.bind.delete_failed"), quote=False
            )
    headers = p_headers.copy()
    headers["X-LC-Session"] = sessiontoken
    get_user_info = await get_url(
        "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/users/me",
        headers=headers,
        fmt="json",
    )
    if get_user_info:
        username = get_user_info.get("nickname", "Guest")
        await PhigrosBindInfo.set_bind_info(sender_id=msg.target.sender_id, session_token=sessiontoken, username=username)
        await msg.send_message(msg.locale.t("phigros.message.bind.success", username=username), quote=False)
    else:
        await msg.send_message(msg.locale.t("phigros.message.bind.failed"))


@phi.command("unbind {{phigros.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await PhigrosBindInfo.remove_bind_info(sender_id=msg.target.sender_id)
    await msg.finish(msg.locale.t("phigros.message.unbind.success"))


@phi.command("b19 {{phigros.help.b19}}")
async def _(msg: Bot.MessageSession):
    bind_info = await PhigrosBindInfo.get_or_none(sender_id=msg.target.sender_id)
    if not bind_info:
        await msg.finish(
            msg.locale.t("phigros.message.user_unbound", prefix=msg.prefixes[0])
        )
    else:
        try:
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
            sort_by_rks = sorted(
                {
                    f"{level}.{song}": game_records[song][level]
                    for song in game_records
                    for level in game_records[song]
                }.items(),
                key=lambda x: x[1]["rks"],
                reverse=True,
            )
            phi_list = [s for s in sort_by_rks if s[1]["score"] == 1000000]
            b19_data = (
                [sorted(phi_list, key=lambda x: x[1]["rks"], reverse=True)[0]]
                if phi_list
                else []
            ) + sort_by_rks[0:19]
            if len(rks_acc := [i[1]["rks"] for i in b19_data]) < 20:
                rks_acc += [0] * (20 - len(rks_acc))
            await msg.finish(
                Image(drawb19(bind_info.username, round(sum(rks_acc) / len(rks_acc), 2), b19_data))
            )
        except Exception as e:
            Logger.error(traceback.format_exc())
            await msg.finish(msg.locale.t("phigros.message.b19.get_failed", err=str(e)))


@phi.command("update", required_superuser=True)
async def _(msg: Bot.MessageSession):
    if await update_assets():
        await msg.finish(msg.locale.t("message.success"))
    else:
        await msg.finish(msg.locale.t("message.failed"))
