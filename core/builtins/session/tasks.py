import asyncio
import time
from typing import Coroutine, TYPE_CHECKING

from core.exports import add_export
from core.logger import Logger

if TYPE_CHECKING:
    from core.builtins.session.internal import MessageSession


class SessionTaskManager:
    """
    消息计划管理器。
    """

    _task_list = {}
    _callback_list = {}

    @classmethod
    def add_task(
        cls,
        msg: "MessageSession",
        flag: asyncio.Event,
        all_: bool = False,
        reply: list[int] | list[str] | int | str | None = None,
        timeout: float | None = 120,
    ):
        sender = msg.session_info.sender_id
        task_type = "reply" if reply else "wait"
        if all_:
            sender = "all"

        if msg.session_info.target_id not in cls._task_list:
            cls._task_list[msg.session_info.target_id] = {}
        if sender not in cls._task_list[msg.session_info.target_id]:
            cls._task_list[msg.session_info.target_id][sender] = {}
        if isinstance(reply, list):
            reply = ",".join(str(mid) for mid in reply)
        elif isinstance(reply, int):
            reply = str(reply)
        cls._task_list[msg.session_info.target_id][sender][msg] = {
            "flag": flag,
            "active": True,
            "type": task_type,
            "reply": reply,
            "ts": time.time(),
            "timeout": timeout,
        }
        Logger.debug(cls._task_list)

    @classmethod
    def add_callback(
        cls,
        message_id: list[int] | list[str] | int | str,
        callback: Coroutine | None,
    ):
        if isinstance(message_id, list):
            message_id = ",".join(str(mid) for mid in message_id)
        elif isinstance(message_id, int):
            message_id = str(message_id)
        cls._callback_list[message_id] = {
            "callback": callback,
            "ts": time.time(),
        }

    @classmethod
    def get_result(cls, msg: "MessageSession"):
        if (
            "result"
            in cls._task_list[msg.session_info.target_id][msg.session_info.sender_id][
                msg
            ]
        ):
            return cls._task_list[msg.session_info.target_id][msg.session_info.sender_id][
                msg
            ]["result"]
        return None

    @classmethod
    def get(cls):
        return cls._task_list

    @classmethod
    async def bg_check(cls):
        for target in cls._task_list:
            for sender in cls._task_list[target]:
                for session in cls._task_list[target][sender]:
                    if cls._task_list[target][sender][session]["active"]:
                        if time.time() - cls._task_list[target][sender][
                            session
                        ]["ts"] > cls._task_list[target][sender][session].get(
                            "timeout", 600
                        ):
                            cls._task_list[target][sender][session]["active"] = False
                            cls._task_list[target][sender][session][
                                "flag"
                            ].set()  # no result = cancel
        for message_id in cls._callback_list.copy():
            if time.time() - cls._callback_list[message_id]["ts"] > 600:
                del cls._callback_list[message_id]

    @classmethod
    async def check(cls, session: "MessageSession"):
        if session.session_info.target_id in cls._task_list:
            senders = []
            if session.session_info.sender_id in cls._task_list[session.session_info.target_id]:
                senders.append(session.session_info.sender_id)
            if "all" in cls._task_list[session.session_info.target_id]:
                senders.append("all")
            if senders:
                for sender in senders:
                    for s in cls._task_list[session.session_info.target_id][sender]:
                        get_ = cls._task_list[session.session_info.target_id][sender][s]
                        if get_["type"] == "wait":
                            get_["result"] = session
                            get_["active"] = False
                            get_["flag"].set()
                        elif get_["type"] == "reply":
                            if session.session_info.reply_id in get_["reply"].split(","):
                                get_["result"] = session
                                get_["active"] = False
                                get_["flag"].set()
        for message_id in cls._callback_list:
            msg_id_lst = message_id.split(",")
            if str(session.session_info.reply_id) in msg_id_lst:
                callback = cls._callback_list[message_id]["callback"]
                if callback:
                    await callback(session)


add_export(SessionTaskManager)

__all__ = ["SessionTaskManager"]
