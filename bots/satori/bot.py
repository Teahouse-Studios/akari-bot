import asyncio
import sys

from launart import Launart
from satori import EventType
from satori.client import Account
from satori.model import ChannelType, Event, LoginStatus

from bots.satori.client import satori_app
from bots.satori.config import SatoriConfig
from bots.satori.context import SatoriContext, SatoriContextManager
from bots.satori.info import (
    client_name,
    sender_prefix,
    sender_prefix_list,
    target_channel_prefix,
    target_prefix_list,
    target_private_prefix,
)
from bots.satori.utils import (
    build_channel_target_id,
    build_private_target_id,
    build_sender_id,
    parse_inbound,
)
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.message.elements import PlainElement
from core.builtins.message.internal import Plain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.builtins.utils import command_prefix
from core.client.init import client_cleanup, client_init
from core.config.base import BaseConfig, CoreConfig
from core.database.models import (
    SenderUnionInfo,
    TargetUnionBind,
    TargetUnionInfo,
    UnfriendlyActionRecords,
)
from core.i18n import Locale
from core.logger import Logger
from core.queue.contracts import ServerAPI
from core.utils.retired import is_retired_client

Bot.register_bot(client_name=client_name)
ctx_id = Bot.register_context_manager(SatoriContextManager)
Bot.register_context_manager(SatoriContextManager, fetch_session=True)

default_locale = BaseConfig.default_locale
ignored_sender = CoreConfig.ignored_sender
enable_tos = CoreConfig.enable_tos
mention_required = CoreConfig.mention_required

# 本平台退役后不再追究针对机器人自身的不友好行为，理由同其它适配器：
# 迁移期间两侧身份可能同属一个 union，在此处封禁会误伤已迁移用户。
client_retired = is_retired_client(client_name)

enable_listening_self_message = SatoriConfig.satori_enable_listening_self_message

STARTUP_TIMEOUT = 120
SHUTDOWN_TIMEOUT = 5

manager = Launart()
app_task: asyncio.Task[None] | None = None
_connected = asyncio.Event()
_fatal = asyncio.Event()
_shutting_down = False


async def _tos_report(sender: str, target: str, reason: str, banned: bool = False):
    try:
        return await ServerAPI.trigger_hook(
            "tos.report",
            session_info=None,
            sender=sender,
            target=target,
            reason=reason,
            banned=banned,
        )
    except Exception:
        Logger.exception(f"tos.report hook failed; report dropped (sender={sender}, target={target}).")
        return None


def _has_content(chain: MessageChain) -> bool:
    for element in chain.values:
        if not isinstance(element, PlainElement):
            return True
        if element.text.strip():
            return True
    return False


def _sender_name(event: Event) -> str | None:
    member = event.member
    user = event.user
    if member is not None and member.nick:
        return member.nick
    if user is not None:
        return user.name or user.nick
    return None


async def _assign_session(
    event: Event,
    messages: MessageChain,
    *,
    target_id: str,
    target_from: str,
    sender_id: str,
    is_private: bool,
    reply_id: str | None,
    bot_id: str,
) -> SessionInfo:
    message = event.message
    return await SessionInfo.assign(
        target_id=target_id,
        target_from=target_from,
        client_name=client_name,
        sender_id=sender_id,
        sender_from=sender_prefix,
        sender_name=_sender_name(event),
        message_id=str(message.id) if message is not None and message.id is not None else None,
        reply_id=reply_id,
        messages=messages,
        is_private=is_private,
        ctx_slot=ctx_id,
        bot_id=bot_id,
        tmp=Temp.data.copy(),
    )


async def message_handler(account: Account, event: Event) -> None:
    message = event.message
    channel = event.channel
    user = event.user
    if message is None or channel is None or user is None:
        return
    is_self = user.id == account.self_id
    if is_self and not enable_listening_self_message:
        return
    if user.is_bot and not is_self:
        return
    bot_id = str(account.self_id)

    platform = event.platform or account.platform or "satori"
    is_private = channel.type == ChannelType.DIRECT
    channel_id = str(channel.id)
    guild_id = str(event.guild.id) if event.guild is not None else str(channel.parent_id or channel.id)

    if is_private:
        target_id = build_private_target_id(platform, user.id)
        target_from = target_private_prefix
    else:
        target_id = build_channel_target_id(platform, guild_id, channel_id)
        target_from = target_channel_prefix
    sender_id = build_sender_id(platform, user.id)
    if sender_id in ignored_sender:
        return

    inbound = parse_inbound(message.content, bot_id)
    if not is_private:
        # 以 @ 他人开头的消息视为与机器人无关
        if inbound.addressed_other and not inbound.at_bot:
            return
        if mention_required and not inbound.at_bot:
            return

    messages = inbound.messages
    if inbound.at_bot and not _has_content(messages):
        messages = MessageChain.assign([Plain(f"{command_prefix[0]}help")])

    session = await _assign_session(
        event,
        messages,
        target_id=target_id,
        target_from=target_from,
        sender_id=sender_id,
        is_private=is_private,
        reply_id=inbound.reply_id,
        bot_id=bot_id,
    )

    if enable_tos and session.target_union_info is not None and session.target_union_info.blocked:
        Logger.debug(f"Satori target {target_id} is blocked, skipped.")
        return

    await Bot.process_message(
        session,
        SatoriContext(
            account=account,
            platform=platform,
            channel_id=channel_id,
            guild_id=None if is_private else guild_id,
            is_private=is_private,
            message_id=str(message.id) if message.id is not None else None,
        ),
    )


async def guild_member_removed_handler(account: Account, event: Event) -> None:
    if not enable_tos or client_retired:
        return
    user = event.user
    if user is None or user.id != account.self_id or event.guild is None:
        return
    operator = event.operator
    if operator is None:
        # 自主退群或协议端未提供操作者时无法归因，不视为不友好行为
        return

    platform = event.platform or account.platform or "satori"
    prefix = f"{target_channel_prefix}|{platform}|{event.guild.id}|"
    binds = await TargetUnionBind.filter(target_id__startswith=prefix)
    if not binds:
        Logger.warning(f"Received kick event from unknown Satori guild {event.guild.id}, dropped.")
        return

    sender_id = build_sender_id(platform, operator.id)
    sender_union_info = await SenderUnionInfo.get_by_sender_id(sender_id)
    blocked_targets: list[str] = []
    for bind in binds:
        target_union_info = await TargetUnionInfo.get_by_target_id(bind.target_id)
        await UnfriendlyActionRecords.create(
            target_id=bind.target_id,
            sender_id=sender_id,
            target_union_id=target_union_info.union_id,
            sender_union_id=sender_union_info.union_id,
            action="kick",
            detail="",
        )
        if sender_union_info.superuser:
            continue
        await target_union_info.edit_attr("blocked", True)
        blocked_targets.append(bind.target_id)

    Logger.info(f"Unfriendly action detected: kick ({event.guild.id})")
    if blocked_targets and not sender_union_info.superuser:
        reason = Locale(default_locale).t("tos.message.reason.kick")
        await _tos_report(sender_id, blocked_targets[0], reason, banned=True)
        await sender_union_info.switch_identity(trust=False)


async def dispatch_event(account: Account, event: Event) -> None:
    try:
        if event.type == EventType.MESSAGE_CREATED:
            await message_handler(account, event)
        elif event.type == EventType.GUILD_MEMBER_REMOVED:
            await guild_member_removed_handler(account, event)
    except asyncio.CancelledError:
        raise
    except Exception:
        Logger.exception(f"Failed to handle Satori event {event.type}: ")


satori_app.register(dispatch_event)


@satori_app.lifecycle
async def on_lifecycle(account: Account, state: LoginStatus) -> None:
    if state in (LoginStatus.ONLINE, LoginStatus.CONNECT):
        _connected.set()
        Logger.info(f"Satori account {account.self_id} ({account.platform}) is {state.name.lower()}.")
        return
    if state == LoginStatus.OFFLINE and not _shutting_down:
        # SDK 在鉴权失败、服务端下线或重连次数耗尽后不再重连，交由守护进程重启本进程
        Logger.error(f"Satori account {account.self_id} went offline and will not reconnect, exiting.")
        _fatal.set()
        return
    Logger.debug(f"Satori account {account.self_id} is {state.name.lower()}.")


async def startup() -> None:
    global app_task
    await client_init(target_prefix_list, sender_prefix_list)
    # run_async 会向 manager 注入 aiohttp 客户端服务与 App 自身
    app_task = asyncio.create_task(
        satori_app.run_async(manager=manager, stop_signal=()),
        name="satori-client",
    )
    try:
        await asyncio.wait_for(_connected.wait(), STARTUP_TIMEOUT)
    except TimeoutError:
        raise RuntimeError("Satori client did not become ready within the startup timeout.") from None


async def shutdown() -> None:
    global _shutting_down, app_task
    _shutting_down = True

    try:
        await SatoriContextManager.shutdown()
    except Exception:
        Logger.exception("Failed to stop Satori typing tasks: ")

    for connection in getattr(satori_app, "connections", []):
        # SDK 把网络层作为 sideload 组件注入，它持有的是局部的 manager 状态，
        # 只有同时置位该状态并关闭连接，重连循环才会退出而不是再次连接。
        local_manager = getattr(connection, "manager", None)
        if local_manager is not None:
            local_manager.status.exiting = True
        socket = getattr(connection, "connection", None)
        if socket is not None and not socket.closed:
            try:
                await socket.close(code=1000)
            except Exception:
                Logger.exception("Failed to close Satori websocket: ")

    manager.status.exiting = True

    task = app_task
    app_task = None
    if task is not None and not task.done():
        try:
            await asyncio.wait_for(task, SHUTDOWN_TIMEOUT)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        except Exception:
            Logger.exception("Satori client stopped with an exception during shutdown: ")
    await client_cleanup()


async def main() -> None:
    exit_code = 0
    try:
        await startup()
        fatal_task = asyncio.create_task(_fatal.wait(), name="satori-fatal")
        try:
            done, _ = await asyncio.wait({app_task, fatal_task}, return_when=asyncio.FIRST_COMPLETED)
            if app_task in done and (error := app_task.exception()) is not None:
                raise error
        finally:
            fatal_task.cancel()
            await asyncio.gather(fatal_task, return_exceptions=True)
        if not app_task.done():
            exit_code = 1
    finally:
        await shutdown()
    if exit_code:
        sys.exit(exit_code)


if SatoriConfig.enable:
    asyncio.run(main())
