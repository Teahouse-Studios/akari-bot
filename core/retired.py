import asyncio
from datetime import datetime, UTC
from pathlib import Path

from core.builtins.message.internal import ActionText, I18NContext, Plain
from core.config.base import CoreConfig
from core.constants.path import retired_path
from core.database.models import StoredData, TargetUnionBind
from core.exports import exports
from core.logger import Logger
from core.utils.random import Random

# 公告文案的基础语言。当前语言缺失时优先回退至此。
NOTICE_FALLBACK_LOCALE = "zh_cn"

# 已发送公告的场景记录，单键存放，避免为每个场景建行而污染存储表。
NOTIFIED_STORED_KEY = "retired_notified"

# 公告延迟推送的区间（秒）。随机取值以错峰：多个场景常在同一时段活跃，
# 固定延迟会让公告集中在同一瞬间涌出，撞上平台频控。
RETIRED_NOTIFY_DELAY_MIN = 300
RETIRED_NOTIFY_DELAY_MAX = 86400

# 已排入延时队列、尚未推送的场景。防止用户在等待期间连发消息导致重复排队。
# 仅存于进程内存，重启即清空；因已发送记录只在推送成功后落库，重启后会自然重排。
pending_notices: set[str] = set()

# 内存态是唯一真相源：判断与写入均走内存，落库时全量覆盖。
# 若改为逐次读库-追加-写回，两个场景并发触发时先写的记录会被覆盖，对应场景将重复收到公告。
_notified: dict[str, str] | None = None
_notified_lock = asyncio.Lock()

# 迁移关系的分隔符，配置形如 "QQ -> QQBot"。
RETIRED_ROUTE_SEPARATOR = "->"

# 退役实例上仍可执行的模块。命令路径与正则路径共用这一份判据，
# 白名单中加入一项，两条路径同时放行。
RETIRED_ALLOWED_MODULES = {"merge"}


def parse_retired_routes(entries: list) -> dict[str, str | None]:
    """
    把 ``"源 -> 目标"`` 形式的配置解析为映射。

    只写源时目标为 None，表示该客户端退役但不提供迁移去处。格式错误的项一律跳过并记录警告，
    不使解析失败：退役是运营配置，一处笔误不应拖垮整个实例的启动。

    :param entries: 配置中的原始条目。
    :return: ``源客户端 → 目标客户端`` 的映射，目标可能为 None。
    """
    routes: dict[str, str | None] = {}
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            continue

        parts = [p.strip() for p in entry.split(RETIRED_ROUTE_SEPARATOR)]
        if len(parts) > 2:
            Logger.warning(f"Invalid retired route {entry!r}: more than one separator, skipped.")
            continue

        source = parts[0]
        if not source:
            Logger.warning(f"Invalid retired route {entry!r}: empty source, skipped.")
            continue

        target = parts[1] if len(parts) == 2 and parts[1] else None
        if source in routes:
            Logger.warning(f"Duplicated retired source {source!r}, the first route is kept.")
            continue

        routes[source] = target
    return routes


RETIRED_ROUTES: dict[str, str | None] = {}
RETIRED_SOURCES: list[str] = []
RETIRED_TARGETS: list[str] = []


def reload_retired_routes() -> None:
    """
    重新解析迁移关系配置。

    解析结果在模块导入时生成一次，命令装饰器的 ``available_for`` 亦在导入期取用，
    因此运行期改动配置须重启才会完全生效。此函数供测试重置内存态。
    """
    global RETIRED_ROUTES
    RETIRED_ROUTES = parse_retired_routes(CoreConfig.retired_clients)
    # 就地改写而非重新赋值：装饰器可能已持有这两个列表对象的引用。
    RETIRED_SOURCES[:] = list(RETIRED_ROUTES.keys())
    RETIRED_TARGETS[:] = list(dict.fromkeys(t for t in RETIRED_ROUTES.values() if t))


reload_retired_routes()


def is_retired_client(client_name: str | None) -> bool:
    """
    判断一个客户端是否已退役。

    :param client_name: 客户端名称，如 ``QQ``。
    :return: 是否已退役。未配置迁移关系时恒为 False。
    """
    if not client_name:
        return False
    return client_name in RETIRED_ROUTES


def is_retired_target(target_id: str | None) -> bool:
    """
    判断一个场景是否属于已退役的客户端。

    场景 ID 形如 ``QQ|Group|12345``，取首段即客户端名称。

    :param target_id: 场景 ID。
    :return: 是否属于已退役客户端。
    """
    if not target_id or "|" not in target_id:
        return False
    return is_retired_client(target_id.split("|")[0])


def is_module_allowed_when_retired(module_name: str | None) -> bool:
    """
    判断一个模块在已退役的客户端上是否仍可执行。

    :param module_name: 模块名称。
    :return: 是否在白名单内。
    """
    if not module_name:
        return False
    return module_name in RETIRED_ALLOWED_MODULES


def is_merge_route_allowed(source_client: str | None, current_client: str | None) -> bool:
    """
    判断一枚迁移码能否在当前客户端兑换。

    命令级 ``available_for`` 只能表达「这个平台是某条迁移关系的目标」，表达不了「这枚迁移码该去哪」。
    配置多条关系时，若不校验来源，甲关系签发的迁移码可在乙关系的目标处兑换。

    :param source_client: 签发迁移码的客户端。
    :param current_client: 兑换所在的客户端。
    :return: 二者是否属于同一条迁移关系。
    """
    if not source_client or not current_client:
        return False
    target = RETIRED_ROUTES.get(source_client)
    return bool(target) and target == current_client


def filter_retired_targets(target_ids: list[str]) -> list[str]:
    """
    从推送目标列表中滤除属于已退役客户端的场景。

    退役客户端停止一切主动推送。在推送目标解析处统一滤除，即可覆盖 RSS、wikilog、schedule
    等全部推送模块，无须逐个模块改动。

    :param target_ids: 待推送的场景 ID 列表。
    :return: 滤除退役场景后的列表。
    """
    return [target_id for target_id in target_ids if not is_retired_target(target_id)]


def should_yield_channel(target_id: str, channels: dict[str, int], channel_id: int) -> bool:
    """
    判断一个退役场景是否应当把消息让给同通道内的其他场景处理。

    退役场景不执行白名单之外的命令，若由它抢到认领，同通道的其他场景会因避让而放弃处理，
    该场景内将无人响应。故只要同通道存在非退役场景，退役场景一律让位。
    通道内只剩自身时照常认领，迁移路径不致中断。

    :param target_id: 当前场景 ID。
    :param channels: 同组内「场景 ID → 通道号」的映射。
    :param channel_id: 当前场景的通道号。
    :return: 是否应当让位。
    """
    if not is_retired_target(target_id):
        return False
    return any(cid == channel_id and tid != target_id and not is_retired_target(tid) for tid, cid in channels.items())


async def is_yielding_retired_session(target_id: str, union_id: str, channel_id: int) -> bool:
    """
    判断一个场景是否为正在让位的退役场景。

    :func:`should_yield_channel` 的查库版本，供手边没有通道映射的介入点调用。非退役场景
    占绝大多数，故先按场景 ID 短路，免得为每条消息白查一次库。

    :param target_id: 当前场景 ID。
    :param union_id: 当前场景所属的 union ID。
    :param channel_id: 当前场景的通道号。
    :return: 是否为正在让位的退役场景。
    """
    if not is_retired_target(target_id) or not union_id:
        return False
    channels = await TargetUnionBind.list_channels(union_id)
    return should_yield_channel(target_id, channels, channel_id)


async def _load_notified() -> dict[str, str]:
    """
    加载已发送公告的场景记录，首次调用时从存储读入并转为字典。

    :return: ``场景 ID → 发送时间`` 的映射。
    """
    global _notified
    if _notified is not None:
        return _notified

    async with _notified_lock:
        # 等锁期间可能已由另一协程完成加载，取得锁后须重新确认。
        if _notified is not None:
            return _notified

        stored = await StoredData.get_or_none(stored_key=NOTIFIED_STORED_KEY)
        records = stored.value if stored and isinstance(stored.value, list) else []
        _notified = {
            r["target_id"]: r.get("timestamp", "") for r in records if isinstance(r, dict) and r.get("target_id")
        }
        return _notified


def reset_notified_cache() -> None:
    """
    清空已发送公告的内存记录，使下次判断重新从存储加载。仅供测试使用。
    """
    global _notified
    _notified = None


async def has_notified(target_id: str) -> bool:
    """
    判断某个场景是否已收到过退役公告。

    :param target_id: 场景 ID。
    :return: 是否已发送过。
    """
    return target_id in await _load_notified()


async def mark_notified(target_id: str) -> None:
    """
    记录某个场景已收到退役公告，并将内存记录全量写回存储。

    :param target_id: 场景 ID。
    """
    notified = await _load_notified()
    notified[target_id] = datetime.now(UTC).isoformat()

    stored, _ = await StoredData.get_or_create(stored_key=NOTIFIED_STORED_KEY, defaults={"value": []})
    stored.value = [{"target_id": tid, "timestamp": ts} for tid, ts in notified.items()]
    await stored.save()


def read_notice(client_name: str, locale: str, base_path: Path | None = None) -> str | None:
    """
    读取某个已退役客户端的公告文案。

    按「当前语言 → 基础语言 → 目录内任意文件」的顺序回退。目录缺失或为空时返回 None，
    由调用方落到通用兜底文案，避免部署方漏放文件时机器人一声不吭。

    :param client_name: 客户端名称，用于定位目录，匹配时转为小写。
    :param locale: 当前会话的语言。
    :param base_path: 公告文案的基础目录，缺省为 ``assets/retired``。测试可传入临时目录。
    :return: 公告正文，无可用文案时为 None。
    """
    base = base_path or retired_path
    directory = base / client_name.lower()
    if not directory.is_dir():
        return None

    candidates = [directory / f"{locale}.txt", directory / f"{NOTICE_FALLBACK_LOCALE}.txt"]
    candidates += sorted(p for p in directory.glob("*.txt") if p not in candidates)

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            Logger.exception(f"Failed to read retired notice from {candidate}: ")
            continue
        if content:
            return content
    return None


def reset_pending_cache() -> None:
    """
    清空待推送队列的内存记录。仅供测试使用。
    """
    pending_notices.clear()


def pick_notice_delay() -> int:
    """
    取一个公告推送的随机延迟秒数。

    :return: 位于 :data:`RETIRED_NOTIFY_DELAY_MIN` 与 :data:`RETIRED_NOTIFY_DELAY_MAX` 之间的秒数。
    """
    return Random.randint(RETIRED_NOTIFY_DELAY_MIN, RETIRED_NOTIFY_DELAY_MAX)


async def should_enqueue_notice(target_id: str) -> bool:
    """
    判断某个场景此刻是否应当排入公告队列。

    :param target_id: 场景 ID。
    :return: 已发送过或已在队列中时为 False。
    """
    if target_id in pending_notices:
        return False
    return not await has_notified(target_id)


def build_notice(client_name: str, locale: str, prefix: str) -> list:
    """
    构造一条退役公告的消息链。

    部署方的文案可在其中书写 ``{I18N:key}`` 引用既有本地化键，故交由 ``t_str`` 处理；
    公告须禁用玩笑，否则文字会被打乱，一份写有停机日期的公告因此失真。

    :param client_name: 客户端名称。
    :param locale: 会话语言。
    :param prefix: 会话的首选命令前缀，供兜底文案使用。
    :return: 消息链。
    """
    content = read_notice(client_name, locale)
    if not content:
        return [
            I18NContext("parser.retired.prompt", prefix=prefix, cmd=ActionText(f"{prefix}merge"), disable_joke=True)
        ]
    return [Plain(content, disable_joke=True)]


async def _deliver_notice(session_info, delay: int) -> None:
    """
    等待指定时长后向场景推送退役公告。

    推送成功才记录已发送：失败多半意味着场景已永久失效（群解散、机器人被移出），
    此时不重试，留待进程重启后由该场景的下条消息重新排队。

    :param session_info: 目标会话信息。
    :param delay: 延迟秒数。
    """
    target_id = session_info.target_id
    try:
        await asyncio.sleep(delay)

        bot = exports["Bot"]
        message = build_notice(
            session_info.client_name,
            session_info.locale.locale,
            session_info.prefixes[0] if session_info.prefixes else "~",
        )
        # 传入单元素会话列表，使按通道归拢只分出一组，公告不会被转投至同通道的其他平台。
        await bot.post_message("*", message, session_list=[session_info])
        await mark_notified(target_id)
        Logger.info(f"Delivered retired notice to {target_id}.")
    except Exception:
        Logger.exception(f"Failed to deliver retired notice to {target_id}: ")
    finally:
        pending_notices.discard(target_id)


async def enqueue_notice(session_info) -> bool:
    """
    为一个场景排入退役公告的延时推送。

    :param session_info: 触发排队的会话信息。
    :return: 是否新排入队列。
    """
    target_id = session_info.target_id
    if not await should_enqueue_notice(target_id):
        return False

    pending_notices.add(target_id)
    delay = pick_notice_delay()
    asyncio.create_task(_deliver_notice(session_info, delay))
    Logger.debug(f"Queued retired notice for {target_id}, delay {delay}s.")
    return True
