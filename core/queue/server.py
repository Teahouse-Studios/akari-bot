"""
服务器队列处理模块。

该模块定义了服务器侧的队列操作接口，以及服务器侧的任务处理器。
服务器通过这个模块向客户端发送各类操作请求，并处理来自客户端的消息和信息。

主要功能：
- 向客户端发送消息、删除消息
- 成员管理操作（限制、踢出、封禁等）
- 消息反应操作（添加/移除emoji反应）
- 上下文管理（保持 / 释放会话上下文）
- 接收客户端的消息并进行处理
- 获取和管理模块信息
- 调用OneBot标准API
- 广播语言文件重载
"""

import asyncio
import re
from typing import TYPE_CHECKING

from core.alive import Alive
from core.builtins.converter import converter
from core.builtins.message.chain import MessageChain, MessageNodes
from core.builtins.parser.command import CommandParser
from core.builtins.parser.message import parser
from core.builtins.session.features import Features
from core.builtins.session.info import SessionInfo
from core.builtins.utils import command_prefix
from core.constants.info import Info
from core.constants.path import PrivateAssets
from core.database.models import JobQueuesTable
from core.exports import exports, add_export
from core.i18n import Locale
from core.loader import ModulesManager
from core.logger import Logger
from core.utils.bash import run_sys_command
from core.web_render import web_render
from .base import JobQueueBase

if TYPE_CHECKING:
    from core.builtins.bot import Bot


class JobQueueServer(JobQueueBase):
    """服务器队列处理类。

    提供服务器向客户端发送各类操作请求的接口方法。这些方法将任务添加到队列，
    由客户端处理后将结果返回给服务器。

    Attributes:
        RELOAD_LOCALE_TIMEOUT: 等待客户端重载语言文件的秒数上限。保活信号只能证明客户端进程还在，
                               不能证明它还在取走队列任务，无上限地等下去会使发起重载的会话一直挂着
    """

    RELOAD_LOCALE_TIMEOUT = 30

    @classmethod
    async def add_job(cls, target_client: str, action, args, wait=True) -> str | dict | None:
        """向队列添加新的任务，目标客户端掉线时直接放弃。

        队列任务须由目标客户端轮询取走，客户端不在线时任务将长期滞留于库中无人认领：
        ``wait=True`` 的调用会就此永久阻塞（所等待的 Event 不会再被置位），
        ``wait=False`` 的调用则只是徒增一条无效记录。因此先查询保活状态，掉线时直接判定失败。

        :param target_client: 目标客户端名称
        :param action: 操作名称
        :param args: 操作参数
        :param wait: 是否等待任务完成（默认 True）

        :return: 同 :meth:`JobQueueBase.add_job`；目标客户端掉线时 ``wait=True`` 返回空字典、
                 ``wait=False`` 返回 None，调用方按「没拿到结果」处理即可
        """
        # 发往自身的任务（如错误上报）无需查询保活状态，服务端不会向自身发送保活信号。
        if target_client and target_client != Info.client_name and not Alive.is_alive(target_client):
            Logger.warning(f"Client {target_client} is offline, skipped action {action}.")
            return {} if wait else None
        return await super().add_job(target_client, action, args, wait=wait)

    @classmethod
    async def client_send_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        quote: bool = True,
        wait=True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ):
        """向客户端发送消息。

        通过队列系统向指定的客户端发送消息。支持引用、消息解析和图片分割等功能。

        :param session_info: 目标会话信息，指定消息发送到哪个场景/用户
        :param message: 要发送的消息链对象
        :param quote: 是否引用原消息（默认 True）
        :param wait: 是否等待消息发送完成（默认 True）
        :param enable_parse_message: 是否解析消息中的特殊标记（默认 True）
        :param enable_split_image: 是否将大图片拆分成多条消息发送（默认 True）

        :return wait=True: 返回发送结果字典（包含 message_id 等）
        :return wait=False: 返回任务 ID
        """
        value = await cls.add_job(
            session_info.client_name,
            "send_message",
            {
                "session_info": converter.unstructure(session_info),
                "message": converter.unstructure(message, MessageChain | MessageNodes),
                "quote": quote,
                "enable_parse_message": enable_parse_message,
                "enable_split_image": enable_split_image,
            },
            wait=wait,
        )
        return value

    @classmethod
    async def client_post_message(
        cls,
        session_info: SessionInfo,
        message: MessageChain | MessageNodes,
        module_name: str = "",
    ):
        """向客户端投递一条主动推送消息。

        与 :meth:`client_send_message` 的区别在于不等待发送结果，并将 `session_info.next_hops`
        一并传递：本跳发送失败时由客户端回调 `post_next_hop`，改由同一条消息通道内的下一个场景重发，
        以保证一条消息通道最终仅送达一次。

        :param session_info: 本跳的目标会话信息，其 `next_hops` 为后备场景 ID 列表
        :param message: 要发送的消息链对象
        :param module_name: 触发推送的模块名称，换跳时需要一并带走

        :return: 任务 ID
        """
        value = await cls.add_job(
            session_info.client_name,
            "post_message",
            {
                "session_info": converter.unstructure(session_info),
                "message": converter.unstructure(message, MessageChain | MessageNodes),
                "module_name": module_name,
            },
            wait=False,
        )
        return value

    @classmethod
    async def client_send_private_message(
        cls,
        session_info: SessionInfo,
        user_id: str,
        message: MessageChain | MessageNodes,
        wait: bool = True,
        enable_parse_message: bool = True,
        enable_split_image: bool = True,
    ):
        """向指定用户单独发送私聊消息。

        通过队列系统让客户端把消息以私聊形式投递给某个用户，消息不会发往 session_info 所指的场景。

        :param session_info: 发起私信的会话信息，用于确定客户端与消息渲染上下文
        :param user_id: 目标用户 ID（带平台前缀，如 `QQ|10000`）
        :param message: 要发送的消息链对象
        :param wait: 是否等待消息发送完成（默认 True，取回消息 ID 需要等待）
        :param enable_parse_message: 是否解析消息中的特殊标记（默认 True）
        :param enable_split_image: 是否将大图片拆分成多条消息发送（默认 True）

        :return wait=True: 返回发送结果字典（包含 message_id，为空列表表示发送失败）
        :return wait=False: 返回任务 ID
        """
        value = await cls.add_job(
            session_info.client_name,
            "send_private_message",
            {
                "session_info": converter.unstructure(session_info),
                "user_id": user_id,
                "message": converter.unstructure(message, MessageChain | MessageNodes),
                "enable_parse_message": enable_parse_message,
                "enable_split_image": enable_split_image,
            },
            wait=wait,
        )
        return value

    @classmethod
    async def client_delete_message(
        cls, session_info: SessionInfo, message_id: str | list[str], reason: str | None = None
    ):
        """删除客户端的消息。

        通过队列系统删除指定的消息。这是一个非阻塞操作。

        :param session_info: 消息所在的会话信息
        :param message_id: 要删除的消息ID或ID列表
        :param reason: 删除原因（可选）

        :return: 任务 ID 或返回值（通常不会被等待）
        """
        if isinstance(message_id, str):
            message_id = [message_id]
        value = await cls.add_job(
            session_info.client_name,
            "delete_message",
            {"session_info": converter.unstructure(session_info), "message_id": message_id, "reason": reason},
            wait=False,
        )
        return value

    @classmethod
    async def client_restrict_member(
        cls, session_info: SessionInfo, user_id: str | list[str], duration: int | None = None, reason: str | None = None
    ):
        """限制场景成员（禁言）。

        通过队列系统对指定的成员进行禁言处理。这是一个非阻塞操作。

        :param session_info: 会话信息
        :param user_id: 要限制的成员 ID 或 ID 列表
        :param duration: 限制时长（秒），None 表示永久
        :param reason: 限制原因（可选）

        :return: 任务 ID 或返回值
        """
        value = await cls.add_job(
            session_info.client_name,
            "restrict_member",
            {
                "session_info": converter.unstructure(session_info),
                "user_id": user_id,
                "duration": duration,
                "reason": reason,
            },
            wait=False,
        )
        return value

    @classmethod
    async def client_unrestrict_member(cls, session_info: SessionInfo, user_id: str | list[str]):
        """解除成员限制（解除禁言）。

        通过队列系统取消之前对成员的限制。这是一个非阻塞操作。

        :param session_info: 会话信息
        :param user_id: 要解除限制的成员 ID 或 ID 列表

        :return: 任务ID或返回值
        """
        value = await cls.add_job(
            session_info.client_name,
            "unrestrict_member",
            {"session_info": converter.unstructure(session_info), "user_id": user_id},
            wait=False,
        )
        return value

    @classmethod
    async def client_kick_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None):
        """踢出场景成员。

        通过队列系统将指定的成员从场景中踢出。这是一个非阻塞操作。

        :param session_info: 会话信息
        :param user_id: 要踢出的成员 ID 或 ID 列表
        :param reason: 踢出原因（可选）

        :return: 任务 ID 或返回值
        """
        value = await cls.add_job(
            session_info.client_name,
            "kick_member",
            {"session_info": converter.unstructure(session_info), "user_id": user_id, "reason": reason},
            wait=False,
        )
        return value

    @classmethod
    async def client_ban_member(cls, session_info: SessionInfo, user_id: str | list[str], reason: str | None = None):
        """永久封禁场景成员。

        通过队列系统永久封禁指定的成员。这是一个非阻塞操作。

        :param session_info: 会话信息
        :param user_id: 要封禁的成员 ID 或 ID 列表
        :param reason: 封禁原因（可选）

        :return: 任务 ID 或返回值
        """
        value = await cls.add_job(
            session_info.client_name,
            "ban_member",
            {"session_info": converter.unstructure(session_info), "user_id": user_id, "reason": reason},
            wait=False,
        )
        return value

    @classmethod
    async def client_unban_member(cls, session_info: SessionInfo, user_id: str | list[str]):
        """解除成员封禁。

        通过队列系统取消之前对成员的永久封禁。这是一个非阻塞操作。

        :param session_info: 会话信息
        :param user_id: 要解除封禁的成员 ID 或 ID 列表

        :return: 任务 ID 或返回值
        """
        value = await cls.add_job(
            session_info.client_name,
            "unban_member",
            {"session_info": converter.unstructure(session_info), "user_id": user_id},
            wait=False,
        )
        return value

    @classmethod
    async def client_add_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str):
        """向消息添加反应。

        通过队列系统在指定的消息上添加表情反应。

        :param session_info: 消息所在的会话信息
        :param message_id: 消息 ID 或 ID 列表
        :param emoji: 要添加的表情代码

        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name,
            "add_reaction",
            {"session_info": converter.unstructure(session_info), "message_id": message_id, "emoji": emoji},
        )
        return value

    @classmethod
    async def client_remove_reaction(cls, session_info: SessionInfo, message_id: str | list[str], emoji: str):
        """从消息移除反应。

        通过队列系统移除指定消息上的表情反应。

        :param session_info: 消息所在的会话信息
        :param message_id: 消息 ID 或 ID 列表
        :param emoji: 要添加的表情代码

        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name,
            "remove_reaction",
            {"session_info": converter.unstructure(session_info), "message_id": message_id, "emoji": emoji},
        )
        return value

    @classmethod
    async def client_start_typing_signal(cls, session_info: SessionInfo):
        """发送“正在输入……”信号。

        通过队列系统向指定会话发送“正在输入……”的状态指示。

        :param session_info: 会话信息
        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name, "start_typing", {"session_info": converter.unstructure(session_info)}
        )
        return value

    @classmethod
    async def client_end_typing_signal(cls, session_info: SessionInfo):
        """隐藏“正在输入……”信号。

        通过队列系统隐藏指定会话的“正在输入……”状态指示。

        :param session_info: 会话信息
        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name, "end_typing", {"session_info": converter.unstructure(session_info)}
        )
        return value

    @classmethod
    async def client_error_signal(cls, session_info: SessionInfo):
        """发送错误信号。

        通过队列系统向指定会话发送错误通知。这是一个非阻塞操作。

        :param session_info: 会话信息
        :return: 任务ID或返回值
        """
        value = await cls.add_job(
            session_info.client_name, "error_signal", {"session_info": converter.unstructure(session_info)}, wait=False
        )
        return value

    @classmethod
    async def client_check_native_permission(cls, session_info: SessionInfo):
        """检查客户端的原生权限。

        通过队列系统检查发送者在该场景中是否拥有原生权限（如管理员权限等）。

        :param session_info: 会话信息
        :return: 布尔值，表示是否拥有权限
        """
        v = await cls.add_job(
            session_info.client_name,
            "check_session_native_permission",
            {"session_info": converter.unstructure(session_info)},
        )
        return v.get("value", False)

    @classmethod
    async def client_hold_context(cls, session_info: SessionInfo):
        """保持会话上下文。

        通过队列系统保持指定会话的上下文，防止其被自动清理。

        :param session_info: 会话信息
        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name, "hold_context", {"session_info": converter.unstructure(session_info)}
        )
        return value

    @classmethod
    async def client_release_context(cls, session_info: SessionInfo):
        """释放会话上下文。

        通过队列系统释放之前保持的会话上下文，允许其被自动清理。

        :param session_info: 会话信息
        :return: 任务结果字典
        """
        value = await cls.add_job(
            session_info.client_name, "release_context", {"session_info": converter.unstructure(session_info)}
        )
        return value

    @classmethod
    async def client_reload_locale(cls, client_name: str, timeout: float | None = None) -> list[str]:
        """通知单个客户端重载语言文件。

        :param client_name: 目标客户端名称
        :param timeout: 等待客户端返回结果的秒数上限，默认为 `RELOAD_LOCALE_TIMEOUT`
        :return: 重载过程中产生的错误信息，客户端掉线时为空列表
        """
        try:
            ret = await asyncio.wait_for(
                cls.add_job(client_name, "reload_locale", {}),
                timeout=timeout if timeout else cls.RELOAD_LOCALE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            Logger.error(f"Timed out waiting for client {client_name} to reload locale.")
            return [f"Timed out waiting for client {client_name} to reload locale."]
        return list(ret.get("err", [])) if ret else []

    @classmethod
    async def client_reload_locale_all(cls) -> list[str]:
        """通知全部在线客户端重载语言文件。

        语言文件在服务端重载后仅对服务端生效，而消息中的 I18NContext 元素是在客户端进程内渲染的，
        因此须逐一通知客户端一并重载，否则实际发出的消息仍为旧文案。

        各客户端读取的是同一批语言文件，产生的错误通常完全一致，因此重复的条目只保留一条。

        :return: 各客户端返回的错误信息
        """
        clients = [client for client in Alive.get_alive() if client != Info.client_name]
        if not clients:
            return []
        results = await asyncio.gather(*[cls.client_reload_locale(client) for client in clients])
        errs = []
        for client_errs in results:
            for err in client_errs:
                if err not in errs:
                    errs.append(err)
        return errs

    @classmethod
    async def call_onebot_api(cls, session_info: SessionInfo, api_name: str, **kwargs: dict):
        """调用 OneBot 标准 API。

        通过队列系统在客户端调用 OneBot 标准 API（如获取群信息、获取群成员列表等）。

        :param session_info: 会话信息
        :param api_name: OneBot API 名称
        :param **kwargs: 传递给 API 的参数

        :return: API 调用的结果字典
        """
        value = await cls.add_job(
            session_info.client_name,
            "call_onebot_api",
            {"session_info": converter.unstructure(session_info), "api_name": api_name, "args": kwargs},
        )
        return value


@JobQueueServer.action("post_next_hop")
async def post_next_hop(tsk: JobQueuesTable, args: dict):
    """主动推送换下一跳。

    客户端投递失败后回调至此。下一跳可能属于另一个平台，只有服务端能够解析其会话信息，
    因此换跳须在服务端进行。跳表长度单调递减，不会形成环路。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 next_hops、message 与 module_name

    :return: 包含 success 标志的字典，跳表耗尽时为 False
    """
    bot: "Bot" = exports["Bot"]
    next_hops = list(args.get("next_hops", []))
    message = converter.structure(args.get("message", {}), MessageChain | MessageNodes)
    module_name = args.get("module_name", "")

    while next_hops:
        target_id = next_hops.pop(0)
        session_info = await bot.fetch_target(target_id)
        if not session_info:
            Logger.warning(f"Failed to fetch next hop {target_id}, skipping to the one after it.")
            continue
        # 掉线客户端无法接收任务，也就不会继续换跳，选中它将导致整条通道就此中断。
        if not Alive.is_alive(session_info.client_name):
            Logger.warning(f"Client {session_info.client_name} is offline, skipping next hop {target_id}.")
            continue
        session_info.next_hops = next_hops
        Logger.info(f"Post message failed, falling back to next hop {target_id}.")
        await JobQueueServer.client_post_message(session_info, message, module_name)
        return {"success": True}

    Logger.warning("Post message failed on every hop of the channel.")
    return {"success": False}


@JobQueueServer.action("receive_message_from_client")
async def receive_message_from_client(tsk: JobQueuesTable, args: dict):
    """接收来自客户端的消息并进行处理。

    这是服务器端的主要消息入口。当客户端接收到用户消息时，会通过队列
    系统将消息转发到服务器，由该处理器进行解析和分发处理。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 session_info

    :return: 包含 success 标志的字典
    """
    await parser(
        await exports["Bot"].MessageSession.from_session_info(
            converter.structure(args.get("session_info", {}), SessionInfo)
        )
    )
    return {"success": True}


@JobQueueServer.action("client_keepalive")
async def client_keepalive(tsk: JobQueuesTable, args: dict):
    """处理客户端的保活信号。

    刷新客户端的存活状态，确保其被认为在线。同时更新可接收消息的前缀列表。

    :param tsk: 任务对象
    :param args: 操作参数（未使用，使用tsk.args代替）

    :return: 包含 success 标志的字典
    """
    Alive.refresh_alive(
        tsk.args["client_name"],
        target_prefix_list=tsk.args.get("target_prefix_list"),
        sender_prefix_list=tsk.args.get("sender_prefix_list"),
        ctx_slot_index=tsk.args.get("ctx_slot_index"),
        features=converter.structure(tsk.args.get("features", {}), Features),
    )
    return {"success": True}


@JobQueueServer.action("trigger_hook")
async def _(tsk: JobQueuesTable, args: dict):
    """触发钩子函数处理器。

    在服务器上执行指定的钩子函数，并返回其执行结果。这允许客户端远程触发服务器上的事件和逻辑。

    :param tsk: 任务对象
    :param args: 操作参数，包含 module_or_hook_name、session_info 和 args

    :return: 包含 result 的字典，其中 result 是钩子函数的返回值
    """
    bot: "Bot" = exports["Bot"]
    session_info: SessionInfo | None = None
    if args.get("session_info"):
        session_info = converter.structure(args["session_info"], SessionInfo)
        await session_info.refresh_info()
    _val = await bot.Hook.trigger(
        args.get("module_or_hook_name", ""), session_info=session_info, args=args.get("args", {})
    )
    Logger.trace(
        f"Trigger hook {args.get('module_or_hook_name', '')} with args {args.get('args', {})}, result: {_val}, type: {type(_val)}"
    )
    await JobQueueServer.return_val(tsk, {"result": _val})


@JobQueueServer.action("client_direct_message")
async def client_direct_message(tsk: JobQueuesTable, args: dict):
    """发送直接消息处理器。

    服务器通过客户端向用户直接发送消息（不通过消息队列）。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 session_info、message 等

    :return: 包含 success 标志的字典
    """
    bot: "Bot" = exports["Bot"]
    session_info = converter.structure(args.get("session_info", {}), SessionInfo)
    await session_info.refresh_info()
    message = converter.structure(args.get("message", {}), MessageChain | MessageNodes)
    await bot.send_direct_message(
        session_info,
        message,
        disable_secret_check=args.get("disable_secret_check", False),
        enable_parse_message=args.get("enable_parse_message", True),
    )
    return {"success": True}


@JobQueueServer.action("get_bot_version")
async def get_bot_version(tsk: JobQueuesTable, args: dict):
    """获取机器人版本信息处理器。

    返回机器人的版本号。如果本地有版本文件则读取，否则尝试从git获取提交哈希。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数操作参数（未使用）

    :return: 包含 version 的字典，version 为版本字符串
    """
    version = None
    version_path = PrivateAssets.path / ".version"
    if version_path.exists():
        with open(version_path, "r") as f:
            version = f.read()
    else:
        returncode, commit_hash, _ = await run_sys_command(["git", "rev-parse", "HEAD"])
        if returncode == 0:
            version = f"git:{commit_hash}"

    return {"version": version}


@JobQueueServer.action("get_web_render_status")
async def get_web_render_status(tsk: JobQueuesTable, args: dict):
    """获取 WebRender 服务状态处理器。

    检查 WebRender 服务是否正常运行。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数（未使用）

    :return: 包含 web_render_status 的字典
    """
    return {"web_render_status": await web_render.browser.check_status()}


@JobQueueServer.action("get_modules_list")
async def get_module_list(tsk: JobQueuesTable, args: dict):
    """获取模块列表处理器。

    获取所有已加载且启用的模块名称列表（不包括基础模块）。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数（未使用）

    :return: 包含 modules_list 的字典
    """
    modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list(use_cache=False).items()}
    modules = {k: v for k, v in modules.items() if v.get("load", True) and not v.get("base", False)}
    module_list = []
    for module in modules.values():
        module_list.append(module["module_name"])
    return {"modules_list": module_list}


@JobQueueServer.action("get_modules_info")
async def get_modules_info(tsk: JobQueuesTable, args: dict):
    """获取所有模块的详细信息处理器。

    获取所有模块的信息并按指定语言进行本地化处理。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 locale（本地化语言）

    :return: 包含 modules 的字典，modules 为模块信息字典
    """
    modules = {k: v.to_dict() for k, v in ModulesManager.return_modules_list(use_cache=False).items()}
    modules = {k: v for k, v in modules.items() if v.get("load", True)}

    for module in modules.values():
        if "desc" in module and module.get("desc"):
            module["desc"] = Locale(args.get("locale", "zh_cn")).t_str(module["desc"])

    return {"modules": modules}


@JobQueueServer.action("get_module_helpdoc")
async def get_module_helpdoc(tsk: JobQueuesTable, args: dict):
    """获取模块帮助文档处理器。

    获取指定模块的详细帮助文档，包括所有命令和正则表达式规则，
    并按指定语言进行本地化。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 module 和 locale

    :return: 包含 help_doc 的字典，help_doc 包含模块名称、描述、命令和正则规则
    """
    module = ModulesManager.modules.get(args.get("module", ""))
    help_doc = {}
    if module:
        help_doc["module_name"] = module.module_name
        module_ = module.to_dict()
        if "desc" in module_ and module_.get("desc"):
            help_doc["desc"] = Locale(args.get("locale", "zh_cn")).t_str(module_["desc"])

        help_ = CommandParser(
            module, module_name=module.module_name, command_prefixes=[command_prefix[0]], is_superuser=True
        )
        help_doc["commands"] = help_.return_json_help_doc(args.get("locale", "zh_cn"))

        regex_ = []
        regex_list = module.regex_list.get(show_required_superuser=True)
        if regex_list:
            for regex in regex_list:
                pattern = None
                if isinstance(regex.pattern, str):
                    pattern = regex.pattern
                elif isinstance(regex.pattern, re.Pattern):
                    pattern = regex.pattern.pattern

                if pattern:
                    rdesc = regex.desc
                    if rdesc:
                        rdesc = Locale(args.get("locale", "zh_cn")).t_str(rdesc)

                    regex_.append({"pattern": pattern, "desc": rdesc})
        help_doc["regexp"] = regex_

    return {"help_doc": help_doc}


@JobQueueServer.action("get_module_related")
async def get_module_related(tsk: JobQueuesTable, args: dict):
    """获取相关模块处理器。

    查找与指定模块相关的其他模块（基于模块的依赖关系）。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 module

    :return: 包含 modules_list 的字典
    """
    return {"modules_list": ModulesManager.search_related_module(args.get("module", ""), include_self=False)}


@JobQueueServer.action("post_module_action")
async def post_module_action(tsk: JobQueuesTable, args: dict):
    """执行模块操作处理器。

    对模块执行操作：加载、卸载或重新加载。

    :param tsk: 任务对象（未使用）
    :param args: 操作参数，包含 module 和 action

        - action: "load"（加载）、"unload"（卸载）或"reload"（重新加载）

    :return: 包含 success 标志的字典
    """
    match args.get("action", ""):
        case "reload":
            status, _ = await ModulesManager.reload_module(args.get("module", ""))
        case "load":
            status = await ModulesManager.load_module(args.get("module", ""))
        case "unload":
            status = await ModulesManager.unload_module(args.get("module", ""))
        case _:
            status = False
    return {"success": status}


add_export(JobQueueServer)
