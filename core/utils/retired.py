import asyncio
from datetime import datetime, UTC
from pathlib import Path

from core.builtins.message.internal import ActionText, I18NContext, Plain
from core.config.base import CoreConfig
from core.constants.path import retired_path
from core.database.models import StoredData, TargetUnionBind
from core.exports import exports
from core.logger import Logger
from core.server.lifecycle import BackgroundTaskLifecycle
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
_notice_tasks: set[asyncio.Task] = globals().get("_notice_tasks", set())

# ``enqueue_notice`` 的判断与占位之间包含首次读取已发记录的 await。若没有互斥，两个并发消息会
# 同时在等待前观察到「未排队」，随后各自创建一项投递任务。锁只覆盖判断与 set 占位，真正的
# 延时投递不在临界区内，不会阻塞其它场景排队。
_notice_enqueue_lock = asyncio.Lock()

# 内存态是唯一真相源：判断与写入均走内存，落库时全量覆盖。
# 若改为逐次读库-追加-写回，两个场景并发触发时先写的记录会被覆盖，对应场景将重复收到公告。
_notified: dict[str, str] | None = None
_notified_lock = asyncio.Lock()
# 公告投递任务可能并发完成。每次持久化都从共享内存字典生成一份快照；若两个 save
# 写入顺序交错时，较早生成的旧快照可能最后落库，使后完成的场景在重启后再次收到公告。
_notified_write_lock = asyncio.Lock()
_MISSING_NOTIFIED = object()

# 迁移关系的分隔符，配置形如 "QQ -> QQBot"。
RETIRED_ROUTE_SEPARATOR = "->"

# 退役实例上仍可执行的模块。命令路径与正则路径共用这一份判据，
# 白名单中加入一项，两条路径同时放行。
# 白名单按用户输入的首词匹配：模块别名可能把某项命令并入其它模块
# （如 merge 现解析为 bind 的 merge 子命令），此时解析出的模块名不属于
# 白名单，退役策略会回退到改写前的首词继续判定。
RETIRED_ALLOWED_MODULES = {"merge"}


def parse_retired_routes(entries: list) -> dict[str, str | None]:
    """把 ``"源 -> 目标"`` 形式的配置解析为映射。

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
    """重新解析迁移关系配置。"""
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
    """判断一个场景是否属于已退役的客户端。

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
    """判断一枚迁移码能否在当前客户端兑换。

    :param source_client: 签发迁移码的客户端。
    :param current_client: 兑换所在的客户端。
    :return: 二者是否属于同一条迁移关系。
    """
    if not source_client or not current_client:
        return False
    target = RETIRED_ROUTES.get(source_client)
    return bool(target) and target == current_client


def filter_retired_targets(target_ids: list[str]) -> list[str]:
    """从推送目标列表中滤除属于已退役客户端的场景。

    :param target_ids: 待推送的场景 ID 列表。
    :return: 滤除退役场景后的列表。
    """
    return [target_id for target_id in target_ids if not is_retired_target(target_id)]


def should_yield_channel(target_id: str, channels: dict[str, int], channel_id: int) -> bool:
    """判断一个退役场景是否应当把消息让给同通道内的其他场景处理。

    :param target_id: 当前场景 ID。
    :param channels: 同组内「场景 ID → 通道号」的映射。
    :param channel_id: 当前场景的通道号。
    :return: 是否应当让位。
    """
    if not is_retired_target(target_id):
        return False
    return any(cid == channel_id and tid != target_id and not is_retired_target(tid) for tid, cid in channels.items())


async def is_yielding_retired_session(target_id: str, union_id: str, channel_id: int) -> bool:
    if not is_retired_target(target_id) or not union_id:
        return False
    channels = await TargetUnionBind.list_channels(union_id)
    return should_yield_channel(target_id, channels, channel_id)


async def _load_notified() -> dict[str, str]:
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
    """清空已发送公告的内存记录，使下次判断重新从存储加载。仅供测试使用。"""
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
    async with _notified_write_lock:
        notified = await _load_notified()
        previous = notified.get(target_id, _MISSING_NOTIFIED)
        notified[target_id] = datetime.now(UTC).isoformat()

        try:
            stored, _ = await StoredData.get_or_create(stored_key=NOTIFIED_STORED_KEY, defaults={"value": []})
            stored.value = [{"target_id": tid, "timestamp": ts} for tid, ts in notified.items()]
            await stored.save()
        except BaseException:
            # 内存态是后续排队判断的真相源。持久化失败时若不回滚，本进程会误以为已经投递，
            # 后续消息将永远无法重试，直到下一次进程重启。
            if previous is _MISSING_NOTIFIED:
                notified.pop(target_id, None)
            else:
                notified[target_id] = previous
            raise


def read_notice(client_name: str, locale: str, base_path: Path | None = None) -> str | None:
    """读取某个已退役客户端的公告文案。

    :param client_name: 客户端名称，用于定位目录，匹配时转为小写。
    :param locale: 当前会话的语言。
    :param base_path: 公告文案的基础目录，缺省为 ``data/retired``。测试可传入临时目录。
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
    """清空待推送队列的内存记录。仅供测试使用。"""
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
    content = read_notice(client_name, locale)
    if not content:
        return [
            I18NContext("parser.retired.prompt", prefix=prefix, cmd=ActionText(f"{prefix}merge"), disable_joke=True)
        ]
    return [Plain(content, disable_joke=True)]


async def _deliver_notice(session_info, delay: int) -> None:
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


def _notice_task_done(task: asyncio.Task, target_id: str) -> None:
    _notice_tasks.discard(task)
    pending_notices.discard(target_id)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        Logger.error(f"Retired notice background task for {target_id} failed: {error!r}")


def _create_notice_task(awaitable, target_id: str) -> asyncio.Task:
    try:
        task = asyncio.create_task(awaitable, name=f"retired-notice-{target_id}")
    except BaseException:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise
    _notice_tasks.add(task)
    task.add_done_callback(lambda done: _notice_task_done(done, target_id))
    return task


async def cancel_retired_notice_tasks() -> None:
    """Cancel and drain delayed notices before queue and database shutdown."""
    current = asyncio.current_task()
    tasks = {task for task in _notice_tasks if task is not current and not task.done()}
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def enqueue_notice(session_info) -> bool:
    """
    为一个场景排入退役公告的延时推送。

    :param session_info: 触发排队的会话信息。
    :return: 是否新排入队列。
    """
    target_id = session_info.target_id
    async with _notice_enqueue_lock:
        if not await should_enqueue_notice(target_id):
            return False
        pending_notices.add(target_id)

    try:
        delay = pick_notice_delay()
        _create_notice_task(_deliver_notice(session_info, delay), target_id)
    except BaseException:
        # 占位成功但任务未能创建时必须释放，否则该场景在本进程余下生命周期内都不会再排队。
        pending_notices.discard(target_id)
        raise
    Logger.debug(f"Queued retired notice for {target_id}, delay {delay}s.")
    return True


BackgroundTaskLifecycle.register_cleanup(
    "core:retired-notice",
    cancel_retired_notice_tasks,
    label="retired notice background tasks",
)
