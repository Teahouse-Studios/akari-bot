import orjson as json

from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import Image, I18NContext, Plain
from core.component import module
from core.constants.path import assets_path
from core.utils.http import get_url
from core.utils.random import Random
from .database.models import PhigrosBindInfo
from .libraries.genb30 import get_b30
from .libraries.update import remove_punctuations, update_assets, p_headers
from .libraries.record import get_game_record

pgr_assets_path = assets_path / "modules" / "phigros"
song_info_path = pgr_assets_path / "song_info.json"

phi = module(
    "phigros",
    developers=["Mivik", "OasisAkari", "DoroWolf"],
    desc="{I18N:phigros.help.desc}",
    alias=["pgr", "phi"],
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
    try:
        get_user_info = await get_url(
            "https://rak3ffdi.cloud.tds1.tapapis.cn/1.1/users/me",
            headers=headers,
            fmt="json",
        )
        if get_user_info:
            username = get_user_info.get("nickname", "Guest")
            await PhigrosBindInfo.set_bind_info(sender_id=msg.session_info.sender_id, session_token=sessiontoken,
                                                username=username)
            await msg.finish(I18NContext("phigros.message.bind.success", username=username), quote=False)
        else:
            await msg.finish(I18NContext("phigros.message.bind.failed"), quote=False)
    except ValueError:
        await msg.finish(I18NContext("phigros.message.bind.failed"), quote=False)


@phi.command("unbind {{I18N:phigros.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await PhigrosBindInfo.remove_bind_info(sender_id=msg.session_info.sender_id)
    await msg.finish(I18NContext("phigros.message.unbind.success"))


@phi.command("b30 {{I18N:phigros.help.b30}}")
async def _(msg: Bot.MessageSession):
    bind_info = await PhigrosBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        await msg.finish(I18NContext("phigros.message.user_unbound", prefix=msg.session_info.prefixes[0]))
    if not song_info_path.exists():
        await msg.finish(I18NContext("phigros.message.file_not_found"))

    img = await get_b30(msg, bind_info.username, bind_info.session_token)
    if img:
        await msg.finish(Image(img))


def get_rank(score: int, full_combo: bool) -> str:
    if score == 1000000:
        return "φ"
    if full_combo:
        return "ν"
    if 960000 <= score <= 999999:
        return "V"
    if 920000 <= score <= 959999:
        return "S"
    if 880000 <= score <= 919999:
        return "A"
    if 820000 <= score <= 879999:
        return "B"
    if 700000 <= score <= 819999:
        return "C"
    if 0 <= score <= 699999:
        return "F"
    return ""


@phi.command("random {{I18N:phigros.help.random}}")
async def _(msg: Bot.MessageSession):
    if not song_info_path.exists():
        await msg.finish(I18NContext("phigros.message.file_not_found"))

    msg_chain = MessageChain.assign()
    with open(song_info_path, "rb") as f:
        song_info = json.loads(f.read())
    sid, sinfo = Random.choice(list(song_info.items()))
    illustration_path = pgr_assets_path / "illustration" / f"{sid.split(".")[0]}.png"
    if illustration_path.exists():
        msg_chain.append(Image(illustration_path))

    msg_chain.append(Plain(sinfo["name"]))
    diff_lst = ["EZ", "HD", "IN", "AT"]
    diffs = [sinfo["diff"][d] for d in diff_lst if d in sinfo["diff"]]
    msg_chain.append(Plain("/".join(diffs)))
    await msg.finish(msg_chain)


@phi.command("score <song_name> {{I18N:phigros.help.score}}")
async def _(msg: Bot.MessageSession, song_name: str):
    bind_info = await PhigrosBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        await msg.finish(I18NContext("phigros.message.user_unbound", prefix=msg.session_info.prefixes[0]))
    if not song_info_path.exists():
        await msg.finish(I18NContext("phigros.message.file_not_found"))

    msg_chain = MessageChain.assign()
    game_records: dict = await get_game_record(msg, bind_info.session_token)
    for sid, record in game_records.items():
        if remove_punctuations(record.get("name").lower()) == remove_punctuations(song_name.lower()):
            illustration_path = pgr_assets_path / "illustration" / f"{sid.split(".")[0]}.png"
            if illustration_path.exists():
                msg_chain.append(Image(illustration_path))

            msg_chain.append(Plain(record.get("name")))
            with open(song_info_path, "rb") as f:
                song_info = json.loads(f.read())
            diff_info = song_info.get(sid, {}).get("diff", {})

            for diff, diff_data in diff_info.items():
                msg_chain.append(Plain(f"{diff} {diff_info[diff]}"))

                diff_data = record.get("diff", {}).get(diff)
                if not diff_data:
                    msg_chain.append(I18NContext("phigros.message.score.no_record"))
                else:
                    score = diff_data["score"]
                    acc = diff_data["accuracy"]
                    full_combo = diff_data["full_combo"]
                    rank = get_rank(score, full_combo)
                    msg_chain.append(Plain(f"{score} {acc:.2f}% {rank}"))
            await msg.finish(msg_chain)
    await msg.finish(I18NContext("phigros.message.music_not_found"))


@phi.command("update [--no-illus]", required_superuser=True)
async def _(msg: Bot.MessageSession):
    if await update_assets(not msg.parsed_msg.get("--no-illus", False)):
        await msg.finish(I18NContext("message.success"))
    await msg.finish(I18NContext("message.failed"))
