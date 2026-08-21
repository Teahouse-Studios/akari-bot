import sys
import uuid

import uvicorn

from bots.web.api import *
from bots.web.client import web_host, available_web_port, forwarded_allow_ips
from bots.web.context import WebContextManager
from bots.web.info import *
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from bots.web.config import WebConfig

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(WebContextManager)

_connected_web_chat_websockets: list[WebSocket] = []


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    _connected_web_chat_websockets.append(websocket)
    Temp.data["web_chat_websocket"] = websocket
    target_id = f"{target_prefix}|0"
    sender_id = f"{sender_prefix}|0"
    try:
        while True:
            rmessage = await websocket.receive_text()
            if rmessage:
                try:
                    message = orjson.loads(rmessage)

                    action = message.get("action")
                    if action == "heartbeat" and message.get("message") == "ping!":
                        Logger.debug("Heartbeat received.")
                        resp = {"action": "heartbeat", "message": "pong!"}
                        await websocket.send_text(orjson.dumps(resp).decode())
                        continue

                    if action == "reaction" and message.get("add"):
                        session = await SessionInfo.assign(
                            target_id=target_id,
                            sender_id=sender_id,
                            sender_name="Console",
                            target_from=target_prefix,
                            is_private=True,
                            sender_from=sender_prefix,
                            client_name=client_name,
                            reply_id=message.get("id"),
                            message_id=str(uuid.uuid4()),
                            messages=MessageChain.assign(message.get("emoji", "")),
                            ctx_slot=ctx_id,
                        )

                        await Bot.process_message(session, {"message": message, "websocket": websocket})
                    elif action == "send":
                        msg_list = message.get("message", [])
                        content = msg_list[0].get("content", "") if msg_list else ""
                        msg_chain = MessageChain.assign(content)
                        session = await SessionInfo.assign(
                            target_id=target_id,
                            sender_id=sender_id,
                            sender_name="Console",
                            target_from=target_prefix,
                            is_private=True,
                            sender_from=sender_prefix,
                            client_name=client_name,
                            message_id=message.get("id", ""),
                            messages=msg_chain,
                            ctx_slot=ctx_id,
                        )

                        await Bot.process_message(session, {"message": message, "websocket": websocket})
                except orjson.JSONDecodeError:
                    continue
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()
    finally:
        _connected_web_chat_websockets[:] = [
            connected for connected in _connected_web_chat_websockets if connected is not websocket
        ]
        # 多个控制台连接可能短暂重叠。非当前连接退出时不能清理新连接；当前连接
        # 退出时则恢复到最近一个仍在线的连接，供主动消息继续使用。
        if Temp.data.get("web_chat_websocket") is websocket:
            if _connected_web_chat_websockets:
                Temp.data["web_chat_websocket"] = _connected_web_chat_websockets[-1]
            else:
                Temp.data.pop("web_chat_websocket", None)


if WebConfig.enable:
    if available_web_port == 0:
        Logger.error("API port is disabled.")
        sys.exit(0)
    if not enable_https:
        Logger.warning("HTTPS is disabled. HTTP mode is insecure and should only be used in trusted environments.")

    uvicorn.run(
        app,
        host=web_host,
        port=available_web_port,
        log_level="info",
        access_log=False,
        forwarded_allow_ips=forwarded_allow_ips,
    )
