from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.internal import ActionText, Image, I18NContext
from core.component import module
from core.logger import Logger
from core.utils.random import Random

from .database.models import PhigrosBindInfo
from .libraries.assets import (
    DIFF_NAMES,
    illustration_path,
    is_legacy_song_info,
    load_song_info,
    match_song,
    song_info_exists,
    update_assets,
)
from .libraries.client import check_session_token, is_token_invalid, phigros_cloud
from .libraries.format import settings_lines, summary_lines, unlock_lines
from .libraries.genb30 import get_b30, get_song_rank
from .libraries.record import get_records, get_save, parse_part

phi = module(
    "phigros",
    developers=["Mivik", "OasisAkari", "DoroWolf"],
    desc="{I18N:phigros.help.desc}",
    alias=["pgr", "phi"],
    doc=True,
)

# 在这些场景绑定会使会话令牌暴露给他人，须先行告警并撤回。
PUBLIC_TARGETS = [
    "Discord|Channel",
    "KOOK|Group",
    "Matrix|Room",
    "QQ|Group",
    "QQBot|Group",
    "QQBot|Guild",
    "Telegram|Group",
    "Telegram|Supergroup",
]


async def _require_bind(msg: Bot.MessageSession):
    """取绑定信息，未绑定则终止命令。

    :param msg: 消息会话。
    """
    bind_info = await PhigrosBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        await msg.finish(
            I18NContext(
                "phigros.message.user_unbound",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}phigros bind"),
            )
        )
    return bind_info


async def _require_song_info(msg: Bot.MessageSession) -> dict:
    """读取曲目信息，尚未初始化或格式过时则终止命令。

    :param msg: 消息会话。
    """
    if not song_info_exists():
        await msg.finish(
            I18NContext(
                "phigros.message.file_not_found",
                prefix=msg.session_info.prefixes[0],
                cmd=ActionText(f"{msg.session_info.prefixes[0]}phigros update"),
            )
        )
    song_info = load_song_info()
    # 旧版曲目 id 与存档中的原始 id 无法对应，放行只会得出全空的成绩，故一并拦下。
    if is_legacy_song_info(song_info):
        await msg.finish(
            I18NContext(
                "phigros.message.file_outdated",
                cmd=ActionText(f"{msg.session_info.prefixes[0]}phigros update"),
            )
        )
    return song_info


async def _fetch_save(msg: Bot.MessageSession, bind_info):
    """取存档，令牌失效时给出可操作的提示。

    :param msg: 消息会话。
    :param bind_info: 绑定信息记录。
    """
    try:
        return await get_save(msg, bind_info)
    except Exception as e:
        Logger.exception()
        if is_token_invalid(e):
            await msg.finish(
                I18NContext(
                    "phigros.message.token_invalid",
                    prefix=msg.session_info.prefixes[0],
                    cmd=ActionText(f"{msg.session_info.prefixes[0]}phigros bind"),
                )
            )
        await msg.finish(I18NContext("phigros.message.fetch_failed"))


def _song_chain(song_id: str, info: dict) -> MessageChain:
    """组装曲目资料。

    :param song_id: 曲目 id。
    :param info: 该曲目的信息结构。
    """
    chain = MessageChain.assign()
    illustration = illustration_path(song_id)
    if illustration:
        chain.append(Image(illustration))
    chain.append(I18NContext("phigros.message.song.title", name=info["name"], artist=info.get("artist", "")))
    if info.get("illustrator"):
        chain.append(I18NContext("phigros.message.song.illustrator", illustrator=info["illustrator"]))
    for level in DIFF_NAMES:
        if level not in info.get("diff", {}):
            continue
        chain.append(
            I18NContext(
                "phigros.message.song.chart",
                difficulty=level,
                constant=info["diff"][level],
                charter=info.get("charter", {}).get(level, "-"),
            )
        )
    return chain


@phi.command(
    "bind <sessiontoken> [-i] {{I18N:phigros.help.bind}}",
    options_desc={"-i": "{I18N:phigros.help.option.i}"},
)
async def _(msg: Bot.MessageSession, sessiontoken: str):
    if msg.session_info.target_from in PUBLIC_TARGETS:
        await msg.send_message(I18NContext("phigros.message.bind.warning"), quote=False)
        await msg.delete()
    if not check_session_token(sessiontoken):
        await msg.finish(I18NContext("phigros.message.bind.invalid_token"), quote=False)

    is_international = bool(msg.parsed_msg.get("-i", False))
    try:
        async with phigros_cloud(sessiontoken, is_international) as cloud:
            username = await cloud.getNickname()
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("phigros.message.bind.failed"), quote=False)

    await PhigrosBindInfo.set_bind_info(
        union_id=msg.session_info.sender_union_id,
        session_token=sessiontoken,
        username=username or "Guest",
        is_international=is_international,
    )
    await msg.finish(I18NContext("phigros.message.bind.success", username=username), quote=False)


@phi.command("unbind {{I18N:phigros.help.unbind}}")
async def _(msg: Bot.MessageSession):
    await PhigrosBindInfo.remove_bind_info(union_id=msg.session_info.sender_union_id)
    await msg.finish(I18NContext("phigros.message.unbind.success"))


@phi.command("refresh {{I18N:phigros.help.refresh}}")
async def _(msg: Bot.MessageSession):
    bind_info = await _require_bind(msg)
    try:
        async with phigros_cloud(bind_info.session_token, bind_info.is_international) as cloud:
            new_token = await cloud.refreshSessionToken()
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("phigros.message.refresh.failed"))

    await PhigrosBindInfo.set_bind_info(
        union_id=msg.session_info.sender_union_id,
        session_token=new_token,
        username=bind_info.username,
        is_international=bind_info.is_international,
    )
    # 新令牌不回显，避免在公开场景再次泄露。
    await msg.finish(I18NContext("phigros.message.refresh.success"), quote=False)


@phi.command("b30 {{I18N:phigros.help.b30}}")
async def _(msg: Bot.MessageSession):
    bind_info = await _require_bind(msg)
    await _require_song_info(msg)
    img = await get_b30(msg, bind_info)
    if img:
        await msg.finish(Image(img))
    await msg.finish(I18NContext("phigros.message.fetch_failed"))


@phi.command("info {{I18N:phigros.help.info}}")
async def _(msg: Bot.MessageSession):
    bind_info = await _require_bind(msg)
    save_data, summary = await _fetch_save(msg, bind_info)
    try:
        progress = parse_part(save_data, "gameProgress")
    except Exception:
        # gameProgress 的结构版本更新只应影响 Data 值一项，其余信息照常输出。
        Logger.exception()
        progress = None
    await msg.finish(
        [I18NContext("phigros.message.info.player", username=bind_info.username)] + summary_lines(summary, progress)
    )


@phi.command("unlock {{I18N:phigros.help.unlock}}")
async def _(msg: Bot.MessageSession):
    bind_info = await _require_bind(msg)
    save_data, _ = await _fetch_save(msg, bind_info)
    try:
        progress = parse_part(save_data, "gameProgress")
        game_key = parse_part(save_data, "gameKey")
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("phigros.message.parse_failed"))
    await msg.finish(unlock_lines(progress, game_key))


@phi.command("settings {{I18N:phigros.help.settings}}")
async def _(msg: Bot.MessageSession):
    bind_info = await _require_bind(msg)
    save_data, _ = await _fetch_save(msg, bind_info)
    try:
        settings = parse_part(save_data, "settings")
    except Exception:
        Logger.exception()
        await msg.finish(I18NContext("phigros.message.parse_failed"))
    await msg.finish(settings_lines(settings))


@phi.command("score <song_name> {{I18N:phigros.help.score}}")
async def _(msg: Bot.MessageSession, song_name: str):
    bind_info = await _require_bind(msg)
    song_info = await _require_song_info(msg)
    matched = match_song(song_info, song_name)
    if not matched:
        await msg.finish(I18NContext("phigros.message.music_not_found"))
    song_id, info = matched

    save_data, _ = await _fetch_save(msg, bind_info)
    records = get_records(save_data, song_info).get(song_id, {})

    chain = MessageChain.assign()
    illustration = illustration_path(song_id)
    if illustration:
        chain.append(Image(illustration))
    chain.append(I18NContext("phigros.message.song.title", name=info["name"], artist=info.get("artist", "")))
    for level in DIFF_NAMES:
        if level not in info.get("diff", {}):
            continue
        record = records.get(level)
        if not record:
            chain.append(I18NContext("phigros.message.score.no_record", difficulty=level, constant=info["diff"][level]))
            continue
        rank = get_song_rank(record["score"], bool(record["fc"]))[0]
        chain.append(
            I18NContext(
                "phigros.message.score.record",
                difficulty=level,
                constant=info["diff"][level],
                score=record["score"],
                acc=f"{record['acc']:.2f}",
                rank=rank,
                rks=f"{record['rks']:.2f}",
            )
        )
    await msg.finish(chain)


@phi.command("song <song_name> {{I18N:phigros.help.song}}")
async def _(msg: Bot.MessageSession, song_name: str):
    song_info = await _require_song_info(msg)
    matched = match_song(song_info, song_name)
    if not matched:
        await msg.finish(I18NContext("phigros.message.music_not_found"))
    await msg.finish(_song_chain(*matched))


@phi.command("random {{I18N:phigros.help.random}}")
async def _(msg: Bot.MessageSession):
    song_info = await _require_song_info(msg)
    await msg.finish(_song_chain(*Random.choice(list(song_info.items()))))


@phi.command("update [--no-illus] {{I18N:phigros.help.update}}", required_superuser=True)
async def _(msg: Bot.MessageSession):
    if await update_assets(not msg.parsed_msg.get("--no-illus", False)):
        await msg.finish(I18NContext("message.success"))
    await msg.finish(I18NContext("message.failed"))
