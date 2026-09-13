"""成绩数据源选择。

舞萌与中二的成绩都可以由水鱼或落雪提供，用户可自行切换；本模块集中维护记录该选择的
``sender_data`` 键，免得各处在会话数据里硬编码字符串。
"""

from core.builtins.bot import Bot
from core.builtins.message.internal import ActionText, I18NContext
from .divingfish_oauth import diving_fish_bind_usable
from ..config import MaimaiConfig, MaimaiSecretConfig
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

# 落雪既未登记用户授权、也没有开发者令牌时，落雪那一侧根本取不到数据。
_LXNS_AVAILABLE = bool(MaimaiConfig.lxns_client_id or MaimaiSecretConfig.lxns_developer_token)

# 中二的历史键名把 chunithm 写成了 chunithum，旧值须继续可读；写回时改用正确拼写。
SOURCE_KEYS = {
    GAME_MAIMAI: ("maimaidx_record_source",),
    GAME_CHUNITHM: ("chunithm_record_source", "chunithum_record_source"),
}


def default_source(game: str) -> str:
    """给出该游戏的默认数据源。

    中二本以落雪为准，但落雪完全不可用时仍以水鱼为准，免得把原本可用的用户挡在绑定提示上。

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
    """写下用户为该游戏选定的数据源。

    :param msg: 消息会话。
    :param game: 游戏标识，取值见 `GAME_*`。
    :param source: `SOURCE_DIVING_FISH` 或 `SOURCE_LXNS`。
    :return: 是否写入成功。
    """
    return await msg.session_info.sender_union_info.edit_sender_data(SOURCE_KEYS[game][0], source)


def toggle_source(current: str) -> str:
    """给出与当前数据源相对的另一者。

    :param current: 当前数据源。
    :return: 另一个数据源。
    """
    return SOURCE_DIVING_FISH if current == SOURCE_LXNS else SOURCE_LXNS


def lxns_bind_usable(
    refresh_token: str | None,
    friend_code: str | None,
    lxns_available: bool = _LXNS_AVAILABLE,
) -> bool:
    """判断一条落雪绑定记录是否可用。

    OAuth 授权过即可用；仅有好友码的旧绑定要走开发者令牌接口，落雪完全没配置时取不到数据。

    :param refresh_token: 该绑定记录的 refresh token。
    :param friend_code: 该绑定记录的好友码。
    :param lxns_available: 落雪是否已登记 OAuth 应用或开发者令牌。
    :return: 是否可用。
    """
    return bool(refresh_token) or (lxns_available and bool(friend_code))


async def is_bound(msg: Bot.MessageSession, game: str, source: str) -> bool:
    """判断用户在该数据源上是否已有可用的绑定。

    舞萌与中二都允许仅凭好友码绑定落雪，这类旧绑定走的是开发者令牌，仍可正常查分。

    :param msg: 消息会话。
    :param game: 游戏标识。
    :param source: 待检查的数据源。
    :return: 是否已绑定。
    """
    if source == SOURCE_DIVING_FISH:
        bind_info = await DivingProberBindInfo.get_by_sender_id(msg, create=False)
        return diving_fish_bind_usable(bind_info)
    bind_info = await LxnsProberBindInfo.get_by_sender_id(msg, create=False)
    if not bind_info:
        return False
    return lxns_bind_usable(bind_info.refresh_token, bind_info.friend_code)


async def switch_source(msg: Bot.MessageSession, game: str, bind_hints: dict[str, str]) -> None:
    """切换该用户在该游戏上的数据源。

    目标数据源尚未绑定时不切换，只提示先绑定：切过去只会得到「未绑定」的报错，不如把原因
    直接说清。

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
