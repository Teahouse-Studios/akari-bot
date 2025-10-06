import sys
import uuid

import uvicorn

from bots.web.api import *
from bots.web.info import *
from bots.web.client import web_host, avaliable_web_port
from bots.web.context import WebContextManager
from core.builtins.bot import Bot
from core.builtins.message.chain import MessageChain
from core.builtins.session.info import SessionInfo
from core.builtins.temp import Temp
from core.config import Config, CFGManager
from core.utils.random import Random

Bot.register_bot(client_name=client_name)

ctx_id = Bot.register_context_manager(WebContextManager)


if not Config("jwt_secret", cfg_type=str, secret=True, table_name="bot_web"):
    CFGManager.write("jwt_secret", Random.randbytes(32).hex(), secret=True, table_name="bot_web")


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    Temp.data["web_chat_websocket"] = websocket
    target_id = f"{target_prefix}|0"
    sender_id = f"{sender_prefix}|0"
    try:
        while True:
            rmessage = await websocket.receive_text()
            if rmessage:
                try:
                    message = json.loads(rmessage)

                    if message["action"] == "heartbeat" and message["message"] == "ping!":
                        Logger.debug("Heartbeat received.")
                        resp = {"action": "heartbeat", "message": "pong!"}
                        await websocket.send_text(json.dumps(resp).decode())
                        continue

                    if message["action"] == "reaction" and message["add"]:
                        session = await SessionInfo.assign(target_id=target_id,
                                                           sender_id=sender_id,
                                                           sender_name="Console",
                                                           target_from=target_prefix,
                                                           sender_from=sender_prefix,
                                                           client_name=client_name,
                                                           reply_id=message["id"],
                                                           message_id=str(uuid.uuid4()),
                                                           messages=MessageChain.assign(message["emoji"]),
                                                           ctx_slot=ctx_id
                                                           )

                        await Bot.process_message(session, message)
                    elif message["action"] == "send":
                        msg_chain = MessageChain.assign(message["message"][0]["content"])
                        session = await SessionInfo.assign(target_id=target_id,
                                                           sender_id=sender_id,
                                                           sender_name="Console",
                                                           target_from=target_prefix,
                                                           sender_from=sender_prefix,
                                                           client_name=client_name,
                                                           message_id=message["id"],
                                                           messages=msg_chain,
                                                           ctx_slot=ctx_id,
                                                           use_url_md_format=True
                                                           )

                        await Bot.process_message(session, message)
                except json.JSONDecodeError:
                    continue
    except WebSocketDisconnect:
        pass
    except Exception:
        Logger.exception()
        await websocket.close()
    finally:
        if "web_chat_websocket" in Temp.data:
            del Temp.data["web_chat_websocket"]


if Config("enable", True, table_name="bot_web"):
    if avaliable_web_port == 0:
        Logger.error("API port is disabled.")
        sys.exit(0)
    if not enable_https:
        Logger.warning("HTTPS is disabled. HTTP mode is insecure and should only be used in trusted environments.")

    uvicorn.run(app, host=web_host, port=avaliable_web_port, log_level="info")
