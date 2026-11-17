"""成绩数据源选择。"""

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from .divingfish_oauth import diving_fish_bind_usable
from ..config import MaimaiConfig
from ..database.models import DivingProberBindInfo, LxnsProberBindInfo

SOURCE_DIVING_FISH = "diving-fish"
SOURCE_LXNS = "lxns"

GAME_MAIMAI = "maimai"
GAME_CHUNITHM = "chunithm"

# 舞萌以水鱼为准，中二以落雪为准；两者都允许用户自行切换。
SOURCE_DEFAULT = {
    GAME_MAIMAI: SOURCE_DIVING_FISH,
    GAME_CHUNITHM: SOURCE_LXNS,
}

# 落雪未登记 OAuth 应用时，落雪那一侧根本取不到数据。
_LXNS_AVAILABLE = bool(MaimaiConfig.lxns_client_id)

# 中二的历史键名把 chunithm 写成了 chunithum，旧值须继续可读；写回时改用正确拼写。
SOURCE_KEYS = {
    GAME_MAIMAI: ("maimaidx_record_source",),
    GAME_CHUNITHM: ("chunithm_record_source", "chunithum_record_source"),
}


def default_source(game: str) -> str:
    """给出该游戏的默认数据源。

    :param game: 游戏标识，取值见 `GAME_*`。
    :return: `SOURCE_DIVING_FISH` 或 `SOURCE_LXNS`。
    """
    if game == GAME_CHUNITHM and not _LXNS_AVAILABLE:
        return SOURCE_DIVING_FISH
    return SOURCE_DEFAULT[game]


def pick_source(msg: Bot.MessageSession, game: str) -> str:
    """读取用户为该游戏选定的数据源，未选定或值非法时取默认值。

    :param msg: 消息会话。
    :param game: 游戏标识，取值见 `GAME_*`。
    :return: `SOURCE_DIVING_FISH` 或 `SOURCE_LXNS`。
    """
    sender_data = msg.session_info.sender_union_info.sender_data or {}
    for key in SOURCE_KEYS[game]:
        source = sender_data.get(key)
        if source in (SOURCE_DIVING_FISH, SOURCE_LXNS):
            return source
    return default_source(game)


async def set_source(msg: Bot.MessageSession, game: str, source: str) -> bool:
    return await msg.session_info.sender_union_info.edit_sender_data(SOURCE_KEYS[game][0], source)


def toggle_source(current: str) -> str:
    """给出与当前数据源相对的另一者。

    :param current: 当前数据源。
    :return: 另一个数据源。
    """
    return SOURCE_DIVING_FISH if current == SOURCE_LXNS else SOURCE_LXNS


def lxns_bind_usable(refresh_token: str | None, lxns_available: bool = _LXNS_AVAILABLE) -> bool:
    """判断一条落雪绑定记录是否可用。

    :param refresh_token: 该绑定记录的 refresh token。
    :param lxns_available: 落雪是否已登记 OAuth 应用。
    :return: 是否可用。
    """
    return bool(refresh_token) and lxns_available


async def is_bound(msg: Bot.MessageSession, game: str, source: str) -> bool:
    if source == SOURCE_DIVING_FISH:
        bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
        return diving_fish_bind_usable(bind_info)
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        return False
    return lxns_bind_usable(bind_info.refresh_token)


async def switch_source(msg: Bot.MessageSession, game: str, bind_hints: dict[str, str]) -> None:
    """切换该用户在该游戏上的数据源。

    :param msg: 消息会话。
    :param game: 游戏标识。
    :param bind_hints: 各数据源对应的绑定命令，用于未绑定时的提示。
    """
    target = toggle_source(pick_source(msg, game))
    if not await is_bound(msg, game, target):
        await msg.finish(
            I18NContext(
                "maimai.message.switch.unbound",
                source=str(
                    I18NContext("maimai.message.source.lx" if target == SOURCE_LXNS else "maimai.message.source.df")
                ),
                cmd=ActionText(bind_hints[target]),
            )
        )
    await set_source(msg, game, target)
    await msg.finish(
        I18NContext(
            "maimai.message.switch",
            source=str(
                I18NContext("maimai.message.source.lx" if target == SOURCE_LXNS else "maimai.message.source.df")
            ),
        )
    )
